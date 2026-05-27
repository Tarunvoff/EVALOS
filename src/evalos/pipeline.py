from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import structlog

from evalos.config import PipelineConfig, RetryConfig
from evalos.criteria import CriteriaGenerator
from evalos.errors import ProviderError
from evalos.eval import Evaluator
from evalos.observability.tracer import RollbackEvent, Trace
from evalos.providers.base import BaseProvider
from evalos.providers.resilient import ResilientProvider
from evalos.repair import RepairEngine
from evalos.rag.agent_eval import AgentReliabilityEvaluator
from evalos.rag.canonical import build_canonical_id_map, canonicalize_claims
from evalos.rag.citation import CitationEvaluator
from evalos.rag.grounding import GroundingEvaluator, _build_claim_map, _extract_claims
from evalos.rag.hallucination import HallucinationDetector
from evalos.rag.dependency import (
    ClaimDependency,
    canonicalize_dependencies,
    validate_dependencies,
)
from evalos.rag.repair_rag import RAGRepairEngine
from evalos.rag.schema import Provenance
from evalos.rag.retriever import CitationMapping, normalize_documents
from evalos.rag.validation import validate_agent_trace, validate_citations
from evalos.types import (
    EvaluationResult,
    GenerationResponse,
    Metrics,
    RepairRecord,
    StreamEvent,
    Usage,
)
from evalos.memory import Memory


class ProviderRegistry:
    _providers: dict[str, type[BaseProvider]] = {}

    @classmethod
    def get(cls, name: str) -> BaseProvider:
        provider_cls = cls._providers.get(name)
        if not provider_cls and name == "litellm":
            from evalos.providers.litellm import LiteLLMProvider

            provider_cls = LiteLLMProvider
            cls._providers[name] = provider_cls
        if not provider_cls:
            raise ValueError(f"Unknown provider: {name}")
        return provider_cls()


class Pipeline:
    def __init__(
        self,
        *,
        model: str,
        provider: str = "litellm",
        repair_strategy: str = "selective",
        max_repairs: int = 2,
        timeout_s: float = 30.0,
        retry: RetryConfig | None = None,
        eval_model: str | None = None,
        criteria_model: str | None = None,
        generation_model: str | None = None,
        repair_model: str | None = None,
        profile: str = "general",
        evaluation_strictness: str = "balanced",
        strict_mode: bool = False,
        provider_instance: BaseProvider | None = None,
        memory: Memory | None = None,
    ) -> None:
        self._config = PipelineConfig(
            model=model,
            provider=provider,
            repair_strategy=repair_strategy,
            max_repairs=max_repairs,
            timeout_s=timeout_s,
            retry=retry or RetryConfig(),
            eval_model=eval_model,
            criteria_model=criteria_model,
            generation_model=generation_model,
            repair_model=repair_model,
            profile=profile,
            evaluation_strictness=evaluation_strictness,
            strict_mode=strict_mode,
        )
        base_provider = provider_instance or ProviderRegistry.get(provider)
        self._provider = ResilientProvider(
            base_provider,
            timeout_s=self._config.timeout_s,
            retry=self._config.retry,
        )
        self._criteria = CriteriaGenerator(self._provider, self._config)
        self._evaluator = Evaluator(self._provider, self._config)
        self._repair = RepairEngine(self._provider, self._config)
        self._grounding = GroundingEvaluator()
        self._hallucination = HallucinationDetector()
        self._citation_eval = CitationEvaluator()
        self._agent_eval = AgentReliabilityEvaluator()
        self._rag_repair = RAGRepairEngine(
            self._provider,
            model=self._config.repair_model or self._config.model,
        )
        self._memory = memory or Memory()
        self._logger = structlog.get_logger("evalos.pipeline")

    async def generate(
        self,
        *,
        query: str,
        optimize_for: list[str],
        domain: str | None = None,
        retrieved_documents: list[dict[str, Any]] | None = None,
        citations: list[dict[str, Any]] | None = None,
        agent_trace: dict[str, Any] | None = None,
        claim_map: dict[str, str] | None = None,
        claim_dependencies: list[dict[str, Any]] | None = None,
    ) -> GenerationResponse:
        start = time.perf_counter()
        domain_name = domain or self._config.profile
        trace = Trace.start(
            model=self._config.model,
            provider=self._config.provider,
            query=query,
            domain=domain_name,
        )
        latency_breakdown: dict[str, float] = {}
        retry_total = 0
        criteria_start = time.perf_counter()
        criteria = await self._criteria.generate(query=query, optimize_for=optimize_for)
        criteria_ms = (time.perf_counter() - criteria_start) * 1000.0
        latency_breakdown["criteria_ms"] = criteria_ms
        trace.criteria = criteria
        trace.add_step(
            "criteria_generated",
            data={"criteria_count": len(criteria)},
            duration_ms=criteria_ms,
        )
        retry_total += self._provider.last_attempts - 1
        strictness_override = self._memory.get_strictness_override(
            model=self._config.model,
            domain=domain_name,
            base_strictness=self._config.evaluation_strictness,
        )
        threshold_overrides = self._memory.get_threshold_overrides(
            criteria=criteria, model=self._config.model, domain=domain_name
        )
        weight_overrides = self._memory.get_weight_overrides(
            criteria=criteria, domain=domain_name
        )

        trace.memory_influence = {
            "strictness": {
                "base": self._config.evaluation_strictness,
                "applied": strictness_override,
            },
            "thresholds_applied": threshold_overrides,
            "weights_applied": weight_overrides,
        }
        trace.add_step(
            "memory_overrides",
            data={
                "strictness": strictness_override,
                "thresholds": list(threshold_overrides.keys()),
                "weights": list(weight_overrides.keys()),
            },
        )

        generation_start = time.perf_counter()
        response = await self._provider.generate(
            model=self._generation_model(), messages=self._messages(query)
        )
        generation_ms = (time.perf_counter() - generation_start) * 1000.0
        latency_breakdown["generation_ms"] = generation_ms
        retry_total += self._provider.last_attempts - 1
        text, usage = _extract_text_and_usage(response)
        trace.initial_text = text
        trace.add_step(
            "generation",
            data={"model": self._generation_model(), "tokens": usage.total_tokens},
            duration_ms=generation_ms,
        )

        rag_text = text
        rag_ms = 0.0
        rag_grounding = None
        rag_hallucination = None
        rag_citation = None
        rag_agent = None
        rag_repair = None
        rag_repair_gain = 0.0
        rag_payload: dict[str, Any] | None = None
        normalized_docs = normalize_documents(retrieved_documents or [])
        normalized_citations = _normalize_citations(citations)

        citation_validation = None
        agent_validation = None
        rag_schema_ok = True
        agent_schema_ok = True
        resolved_claim_map: dict[str, str] | None = claim_map
        dependency_errors: list[str] = []
        dependency_models: list[ClaimDependency] = []
        canonical_claims: list[dict[str, object]] = []
        external_to_canonical: dict[str, str] = {}
        claim_provenance = Provenance(origin="caller" if claim_map else "generated")

        if resolved_claim_map is None and (citations is not None or claim_dependencies or normalized_docs):
            resolved_claim_map = _build_claim_map(_extract_claims(rag_text))
        if resolved_claim_map:
            canonical_items = canonicalize_claims(
                claim_map=resolved_claim_map,
                provided_order=sorted(resolved_claim_map.keys()),
                provenance=claim_provenance,
            )
            external_to_canonical = build_canonical_id_map(canonical_items)
            canonical_claims = [
                {
                    "canonical_claim_id": item.canonical_claim_id,
                    "external_claim_id": item.external_claim_id,
                    "internal_claim_index": item.internal_claim_index,
                }
                for item in canonical_items
            ]
            trace.claim_canonicalization = canonical_claims
        canonical_claims: list[dict[str, object]] = []
        external_to_canonical: dict[str, str] = {}
        claim_provenance = Provenance(origin="caller" if claim_map else "generated")

        if resolved_claim_map is None and (citations is not None or claim_dependencies or normalized_docs):
            resolved_claim_map = _build_claim_map(_extract_claims(rag_text))
        if resolved_claim_map:
            canonical_items = canonicalize_claims(
                claim_map=resolved_claim_map,
                provided_order=sorted(resolved_claim_map.keys()),
                provenance=claim_provenance,
            )
            external_to_canonical = build_canonical_id_map(canonical_items)
            canonical_claims = [
                {
                    "canonical_claim_id": item.canonical_claim_id,
                    "external_claim_id": item.external_claim_id,
                    "internal_claim_index": item.internal_claim_index,
                }
                for item in canonical_items
            ]
            trace.claim_canonicalization = canonical_claims

        if citations is not None:
            if not normalized_docs:
                rag_schema_ok = False
                trace.schema_validation.append(
                    {
                        "source": "citations",
                        "status": "failed",
                        "errors": ["missing_retrieved_documents"],
                    }
                )
                trace.add_step(
                    "schema_validation_failed",
                    data={"source": "citations", "reason": "missing_documents"},
                )
                normalized_citations = []
            else:
                citation_validation = validate_citations(
                    retrieved_documents=normalized_docs,
                    generated_response=rag_text,
                    citations=normalized_citations,
                    claim_map=resolved_claim_map,
                )
                resolved_claim_map = citation_validation.claim_map
                trace.schema_validation.append(
                    {
                        "source": "citations",
                        "status": "passed" if citation_validation.valid else "failed",
                        "repaired": citation_validation.repaired,
                        "error_count": len(citation_validation.errors),
                    }
                )
                if citation_validation.errors:
                    trace.add_step(
                        "schema_validation",
                        data={
                            "source": "citations",
                            "errors": [error.code for error in citation_validation.errors],
                        },
                    )
                if not citation_validation.valid:
                    rag_schema_ok = False
                normalized_citations = (
                    citation_validation.citations if citation_validation.valid else []
                )

        if agent_trace is not None:
            agent_validation = validate_agent_trace(agent_trace=agent_trace)
            trace.schema_validation.append(
                {
                    "source": "agent_trace",
                    "status": "passed" if agent_validation.valid else "failed",
                    "repaired": agent_validation.repaired,
                    "error_count": len(agent_validation.errors),
                }
            )
            if agent_validation.errors:
                trace.add_step(
                    "schema_validation",
                    data={
                        "source": "agent_trace",
                        "errors": [error.code for error in agent_validation.errors],
                    },
                )
            if not agent_validation.valid:
                agent_schema_ok = False

        trace.provenance = {
            "claims": "caller" if claim_map else "generated",
            "citations": "caller" if citations is not None else "none",
            "agent_trace": "caller" if agent_trace is not None else "none",
            "repairs": "selective",
            "memory": "adaptive",
            "schema_version": trace.schema_version,
        }

        trace.provenance = {
            "claims": "caller" if claim_map else "generated",
            "citations": "caller" if citations is not None else "none",
            "agent_trace": "caller" if agent_trace is not None else "none",
            "repairs": "selective",
            "memory": "adaptive",
            "schema_version": trace.schema_version,
        }

        if claim_dependencies:
            dependency_models = [ClaimDependency.model_validate(item) for item in claim_dependencies]
            if resolved_claim_map:
                dependency_errors = validate_dependencies(
                    claim_ids=set(resolved_claim_map.keys()),
                    dependencies=dependency_models,
                )
            if dependency_errors:
                trace.schema_validation.append(
                    {
                        "source": "claim_dependencies",
                        "status": "failed",
                        "errors": dependency_errors,
                    }
                )
                trace.add_step(
                    "schema_validation",
                    data={"source": "claim_dependencies", "errors": dependency_errors},
                )
            if external_to_canonical:
                trace.claim_dependencies = [
                    item.model_dump()
                    for item in canonicalize_dependencies(
                        dependencies=dependency_models,
                        external_to_canonical=external_to_canonical,
                    )
                ]
            if external_to_canonical:
                trace.claim_dependencies = [
                    item.model_dump()
                    for item in canonicalize_dependencies(
                        dependencies=dependency_models,
                        external_to_canonical=external_to_canonical,
                    )
                ]

        if normalized_docs and rag_schema_ok:
            trace.retrieval_inputs = _rag_doc_summaries(normalized_docs)
            rag_start = time.perf_counter()
            rag_grounding = self._grounding.evaluate(
                retrieved_documents=normalized_docs,
                generated_response=rag_text,
                citations=normalized_citations,
                claim_map=resolved_claim_map,
                dependencies=[item.model_dump() for item in dependency_models],
            )
            rag_hallucination = self._hallucination.evaluate(grounding=rag_grounding)
            rag_citation = self._citation_eval.evaluate(
                retrieved_documents=normalized_docs,
                citations=normalized_citations,
                grounding=rag_grounding,
                claim_map=resolved_claim_map,
            )
            if (
                rag_grounding.unsupported_claims
                or rag_hallucination.hallucinated_spans
                or rag_citation.missing_citations
            ):
                rag_repair = await self._rag_repair.repair(
                    response_text=rag_text,
                    retrieved_documents=normalized_docs,
                    grounding=rag_grounding,
                    hallucination=rag_hallucination,
                    citations=normalized_citations,
                    citation_eval=rag_citation,
                )
                if rag_repair.applied:
                    rag_text = rag_repair.repaired_text
                    updated_grounding = self._grounding.evaluate(
                        retrieved_documents=normalized_docs,
                        generated_response=rag_text,
                        citations=normalized_citations,
                        claim_map=resolved_claim_map,
                        dependencies=[item.model_dump() for item in dependency_models],
                    )
                    rag_repair_gain = (
                        updated_grounding.grounding_score - rag_grounding.grounding_score
                    )
                    rag_grounding = updated_grounding
                    rag_hallucination = self._hallucination.evaluate(grounding=rag_grounding)
                    rag_citation = self._citation_eval.evaluate(
                        retrieved_documents=normalized_docs,
                        citations=normalized_citations,
                        grounding=rag_grounding,
                        claim_map=resolved_claim_map,
                    )
            rag_ms = (time.perf_counter() - rag_start) * 1000.0
            latency_breakdown["rag_ms"] = rag_ms
            trace.grounding = rag_grounding.model_dump()
            trace.hallucination = rag_hallucination.model_dump()
            trace.citation = rag_citation.model_dump()
            if not trace.claim_canonicalization:
                trace.claim_canonicalization = rag_grounding.canonical_claims
            if dependency_models and not trace.claim_dependencies:
                trace.claim_dependencies = [item.model_dump() for item in dependency_models]
            if rag_repair:
                trace.rag_repair = rag_repair.model_dump()
            trace.add_step(
                "rag_evaluation",
                data={
                    "grounding_score": rag_grounding.grounding_score,
                    "hallucination_score": rag_hallucination.hallucination_score,
                    "citation_accuracy": rag_citation.citation_accuracy_score,
                    "citation_precision": rag_citation.citation_precision,
                    "repair_applied": bool(rag_repair and rag_repair.applied),
                },
                duration_ms=rag_ms,
            )
        elif normalized_docs and not rag_schema_ok:
            trace.add_step(
                "rag_evaluation_skipped",
                data={"reason": "schema_validation_failed"},
            )

        if agent_trace and agent_schema_ok and agent_validation is not None:
            rag_agent = self._agent_eval.evaluate(trace=agent_validation.trace)
            trace.agent_evaluation = rag_agent.model_dump()
            trace.agent_trace = agent_validation.trace.model_dump()
            trace.add_step(
                "agent_evaluation",
                data={
                    "tool_correctness": rag_agent.tool_correctness_score,
                    "planning_score": rag_agent.planning_score,
                    "execution_alignment": rag_agent.execution_alignment_score,
                    "hallucinated_tool_usage": rag_agent.hallucinated_tool_usage,
                    "hallucinated_tool_usage_rate": rag_agent.hallucinated_tool_usage_rate,
                    "reasoning_consistency": rag_agent.reasoning_consistency_score,
                },
            )
        elif agent_trace and not agent_schema_ok:
            trace.add_step(
                "agent_evaluation_skipped",
                data={"reason": "schema_validation_failed"},
            )

        if rag_grounding or rag_agent:
            await self._memory.arecord_rag_signals(
                model=self._config.model,
                domain=domain_name,
                grounding_score=rag_grounding.grounding_score if rag_grounding else 1.0,
                hallucination_score=rag_hallucination.hallucination_score
                if rag_hallucination
                else 0.0,
                citation_accuracy=rag_citation.citation_accuracy_score if rag_citation else 1.0,
                tool_correctness=rag_agent.tool_correctness_score if rag_agent else None,
                weight=1.0,
            )
            rag_payload = {
                "grounding": rag_grounding.model_dump() if rag_grounding else None,
                "hallucination": rag_hallucination.model_dump() if rag_hallucination else None,
                "citation": rag_citation.model_dump() if rag_citation else None,
                "agent": rag_agent.model_dump() if rag_agent else None,
                "repair": rag_repair.model_dump() if rag_repair else None,
                "canonical_claims": rag_grounding.canonical_claims if rag_grounding else None,
                "claim_dependencies": [item.model_dump() for item in dependency_models]
                if dependency_models
                else None,
            }
        elif citation_validation or agent_validation:
            rag_payload = {
                "schema_validation": {
                    "citations": citation_validation.model_dump()
                    if citation_validation
                    else None,
                    "agent_trace": agent_validation.model_dump()
                    if agent_validation
                    else None,
                }
            }

        evaluation_start = time.perf_counter()
        evaluation = await self._evaluator.evaluate(
            query=query,
            response_text=rag_text,
            criteria=criteria,
            strictness_override=strictness_override,
            threshold_overrides=threshold_overrides,
            weight_overrides=weight_overrides,
        )
        evaluation_ms = (time.perf_counter() - evaluation_start) * 1000.0
        latency_breakdown["evaluation_ms"] = evaluation_ms
        retry_total += self._provider.last_attempts - 1
        quality_before = evaluation.weighted_score
        trace.evaluation = evaluation
        trace.add_step(
            "evaluation",
            data={
                "score": evaluation.weighted_score,
                "passed": evaluation.passed,
                "failed": evaluation.failed,
            },
            duration_ms=evaluation_ms,
        )

        memory_start = time.perf_counter()
        await self._memory.arecord_evaluation(
            model=self._config.model,
            domain=domain_name,
            criteria=criteria,
            evaluation=evaluation,
            stability_score=1.0,
        )
        await self._memory.arecord_section_outcome(
            section_ids_all=[section.id for section in evaluation.sections],
            failed_section_ids=_collect_failed_sections(evaluation),
            attempt=0,
        )
        memory_ms = (time.perf_counter() - memory_start) * 1000.0
        latency_breakdown["memory_ms"] = memory_ms
        trace.add_step("memory_recorded", duration_ms=memory_ms)

        repairs: list[RepairRecord] = []
        current_text = rag_text
        current_eval = evaluation
        locked_sections: set[str] = set()
        rollback_count = 0
        rollback_events: list[RollbackEvent] = []
        repair_overrides: list[dict[str, object]] = []

        for attempt in range(1, self._config.max_repairs + 1):
            if current_eval.passed:
                break
            if self._config.repair_strategy != "selective":
                break
            failed_sections_now = _collect_failed_sections(current_eval)
            stable_sections = self._memory.get_stable_sections(
                [section.id for section in current_eval.sections]
            )
            locked_sections.update(
                [section_id for section_id in stable_sections if section_id not in failed_sections_now]
            )
            strategy_overrides = self._memory.get_strategy_overrides(current_eval.failed)
            if strategy_overrides:
                repair_overrides.append(
                    {
                        "attempt": attempt,
                        "criteria": sorted(strategy_overrides.keys()),
                        "strategy": next(iter(strategy_overrides.values()), ""),
                    }
                )

            repair_start = time.perf_counter()
            repaired, deltas, strategies, failed_sections, repair_tokens = await self._repair.repair(
                query=query,
                response_text=current_text,
                evaluation=current_eval,
                criteria=criteria,
                sections=current_eval.sections,
                locked_sections=locked_sections,
                strategy_overrides=strategy_overrides,
            )
            repair_ms = (time.perf_counter() - repair_start) * 1000.0
            latency_breakdown["repair_ms"] = latency_breakdown.get("repair_ms", 0.0) + repair_ms
            retry_total += self._provider.last_attempts - 1
            trace.add_step(
                "repair_attempt",
                data={
                    "attempt": attempt,
                    "failed_criteria": current_eval.failed,
                    "strategies": strategies,
                    "failed_sections": failed_sections,
                    "repair_tokens": repair_tokens,
                },
                duration_ms=repair_ms,
            )

            reevaluate_start = time.perf_counter()
            new_eval = await self._evaluator.evaluate(
                query=query,
                response_text=repaired,
                criteria=criteria,
                strictness_override=strictness_override,
                threshold_overrides=threshold_overrides,
                weight_overrides=weight_overrides,
            )
            reevaluate_ms = (time.perf_counter() - reevaluate_start) * 1000.0
            latency_breakdown["reevaluation_ms"] = latency_breakdown.get("reevaluation_ms", 0.0) + reevaluate_ms
            retry_total += self._provider.last_attempts - 1
            trace.add_step(
                "repair_evaluation",
                data={
                    "attempt": attempt,
                    "score": new_eval.weighted_score,
                    "passed": new_eval.passed,
                    "failed": new_eval.failed,
                },
                duration_ms=reevaluate_ms,
            )

            if new_eval.weighted_score < current_eval.weighted_score:
                self._logger.info(
                    "repair_degraded_score_rollback",
                    score_before=current_eval.weighted_score,
                    score_after=new_eval.weighted_score,
                )
                rollback_count += 1
                rollback_events.append(
                    RollbackEvent(
                        attempt=attempt,
                        score_before=current_eval.weighted_score,
                        score_after=new_eval.weighted_score,
                        timestamp=time.time(),
                        reason="repair_degraded_score",
                    )
                )
                trace.add_step(
                    "repair_rollback",
                    data={
                        "attempt": attempt,
                        "score_before": current_eval.weighted_score,
                        "score_after": new_eval.weighted_score,
                    },
                )
                rollback_weight = _evaluation_confidence(new_eval) * 0.4
                await self._memory.arecord_repair(
                    strategies=strategies,
                    success=False,
                    weight=rollback_weight,
                )
                await self._memory.arecord_section_outcome(
                    section_ids_all=[section.id for section in new_eval.sections],
                    failed_section_ids=_collect_failed_sections(new_eval),
                    attempt=attempt,
                    rollback=True,
                )
                break

            locked_sections.update(failed_sections)
            success = new_eval.passed or (
                len(new_eval.failed) < len(current_eval.failed)
                and new_eval.weighted_score >= current_eval.weighted_score
            )
            stability_score = _stability_score(current_eval, new_eval)
            repair_weight = _evaluation_confidence(new_eval) * stability_score
            await self._memory.arecord_repair(
                strategies=strategies,
                success=success,
                weight=repair_weight,
            )
            await self._memory.arecord_section_outcome(
                section_ids_all=[section.id for section in new_eval.sections],
                failed_section_ids=_collect_failed_sections(new_eval),
                attempt=attempt,
            )
            await self._memory.arecord_evaluation(
                model=self._config.model,
                domain=domain_name,
                criteria=criteria,
                evaluation=new_eval,
                stability_score=stability_score,
            )

            repairs.append(
                RepairRecord(
                    attempt=attempt,
                    failed_criteria=current_eval.failed,
                    repaired_text=repaired,
                    strategies=strategies,
                    failed_sections=failed_sections,
                    score_before=current_eval.weighted_score,
                    score_after=new_eval.weighted_score,
                    deltas=deltas,
                    repair_tokens=repair_tokens,
                    token_delta=repair_tokens,
                    provenance=Provenance(
                        origin="repair",
                        derived_from=current_eval.failed,
                        repair_generation=attempt,
                    ),
                )
            )
            current_text = repaired
            current_eval = new_eval

            self._logger.info(
                "repair_applied",
                attempt=attempt,
                failed_criteria=repairs[-1].failed_criteria,
                strategies=repairs[-1].strategies,
                affected_sections=repairs[-1].failed_sections,
                score_before=repairs[-1].score_before,
                score_after=repairs[-1].score_after,
                token_delta=repairs[-1].token_delta,
            )

        latency_ms = (time.perf_counter() - start) * 1000.0
        latency_breakdown["total_ms"] = latency_ms
        quality_after = current_eval.weighted_score if current_eval else 0.0
        repair_gain = quality_after - quality_before
        repair_efficiency = repair_gain / max(1, len(repairs))
        token_efficiency = repair_gain / max(1, usage.total_tokens)
        repair_token_cost = sum(record.repair_tokens for record in repairs)
        estimated_full_retry_tokens = usage.total_tokens * len(repairs)
        tokens_saved_vs_retry = max(0.0, estimated_full_retry_tokens - repair_token_cost)
        adaptation = self._memory.get_adaptation_metrics()
        decay = self._memory.get_decay_analytics(model=self._config.model, domain=domain_name)
        readiness = self._memory.get_adaptation_readiness(
            model=self._config.model, domain=domain_name
        )
        threshold_drift = _threshold_drift(criteria, threshold_overrides)
        metrics = Metrics(
            provider=self._config.provider,
            model=self._config.model,
            latency_ms=latency_ms,
            retries=retry_total,
            repairs=len(repairs),
            usage=usage,
            criteria_count=len(criteria),
            failed_criteria_count=len(current_eval.failed) if current_eval else 0,
            quality_before=quality_before,
            quality_after=quality_after,
            repair_gain=repair_gain,
            repair_efficiency=repair_efficiency,
            token_efficiency=token_efficiency,
            criteria_pass_rate=current_eval.pass_rate if current_eval else 0.0,
            weighted_quality_score=quality_after,
            repair_lineage=repairs,
            tokens_saved_vs_retry=tokens_saved_vs_retry,
            estimated_full_retry_tokens=estimated_full_retry_tokens,
            repair_token_cost=repair_token_cost,
            improvement_delta=repair_gain,
            adaptation_strength=_adaptation_strength(adaptation),
            threshold_drift=threshold_drift,
            decay_effect=_decay_effect(decay),
            rollback_frequency=rollback_count / max(1, self._config.max_repairs),
            memory_confidence=_evaluation_confidence(current_eval),
            adaptation_ready=readiness.get("ready", False),
            adaptation_metrics={
                "adaptation": adaptation,
                "decay": decay,
                "readiness": readiness,
            },
            grounding_score=rag_grounding.grounding_score if rag_grounding else 0.0,
            hallucination_rate=rag_hallucination.hallucination_score
            if rag_hallucination
            else 0.0,
            citation_accuracy=rag_citation.citation_accuracy_score if rag_citation else 0.0,
            citation_precision=rag_citation.citation_precision if rag_citation else 0.0,
            tool_correctness_score=rag_agent.tool_correctness_score if rag_agent else 0.0,
            agent_planning_score=rag_agent.planning_score if rag_agent else 0.0,
            execution_alignment_score=rag_agent.execution_alignment_score if rag_agent else 0.0,
            hallucinated_tool_usage_rate=rag_agent.hallucinated_tool_usage_rate if rag_agent else 0.0,
            reasoning_consistency_score=rag_agent.reasoning_consistency_score if rag_agent else 0.0,
            retrieval_alignment_score=rag_grounding.grounding_score if rag_grounding else 0.0,
            rag_repair_gain=rag_repair_gain,
        )

        trace.repairs = repairs
        trace.rollback_events = rollback_events
        trace.final_text = current_text
        trace.outcome = "passed" if current_eval and current_eval.passed else "failed"
        trace.latency_ms = latency_ms
        trace.latency_breakdown = latency_breakdown
        trace.token_usage = Usage(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens + repair_token_cost,
        )
        trace.memory_influence.update(
            {
                "repair_bias": repair_overrides,
                "adaptation": adaptation,
                "decay": decay,
                "readiness": readiness,
            }
        )
        trace.add_step("request_complete", data={"outcome": trace.outcome})

        self._logger.info(
            "generation_complete",
            model=self._config.model,
            provider=self._config.provider,
            latency_ms=latency_ms,
            repairs=len(repairs),
            passed=current_eval.passed,
        )

        return GenerationResponse(
            text=current_text,
            initial_text=text,
            raw=response,
            evaluation=current_eval,
            repairs=repairs,
            metrics=metrics,
            trace=trace,
            rag=rag_payload,
        )

    async def stream(
        self,
        *,
        query: str,
        optimize_for: list[str],
        domain: str | None = None,
        retrieved_documents: list[dict[str, Any]] | None = None,
        citations: list[dict[str, Any]] | None = None,
        agent_trace: dict[str, Any] | None = None,
        claim_map: dict[str, str] | None = None,
        claim_dependencies: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        domain_name = domain or self._config.profile
        trace = Trace.start(
            model=self._config.model,
            provider=self._config.provider,
            query=query,
            domain=domain_name,
        )
        criteria_start = time.perf_counter()
        criteria = await self._criteria.generate(query=query, optimize_for=optimize_for)
        criteria_ms = (time.perf_counter() - criteria_start) * 1000.0
        trace.criteria = criteria
        trace.add_step(
            "criteria_generated",
            data={"criteria_count": len(criteria)},
            duration_ms=criteria_ms,
        )
        strictness_override = self._memory.get_strictness_override(
            model=self._config.model,
            domain=domain_name,
            base_strictness=self._config.evaluation_strictness,
        )
        threshold_overrides = self._memory.get_threshold_overrides(
            criteria=criteria, model=self._config.model, domain=domain_name
        )
        weight_overrides = self._memory.get_weight_overrides(
            criteria=criteria, domain=domain_name
        )
        trace.memory_influence = {
            "strictness": {
                "base": self._config.evaluation_strictness,
                "applied": strictness_override,
            },
            "thresholds_applied": threshold_overrides,
            "weights_applied": weight_overrides,
        }
        trace.add_step(
            "memory_overrides",
            data={
                "strictness": strictness_override,
                "thresholds": list(threshold_overrides.keys()),
                "weights": list(weight_overrides.keys()),
            },
        )

        stream_start = time.perf_counter()
        stream = self._provider.stream(
            model=self._generation_model(), messages=self._messages(query)
        )
        buffer: list[str] = []

        async for event in stream:
            if event.type == "text":
                delta = _extract_stream_delta(event.data)
                if delta:
                    buffer.append(delta)
                    yield StreamEvent(type="text", data=delta)
            if event.type == "done":
                break

        text = "".join(buffer)
        trace.initial_text = text
        trace.add_step(
            "generation",
            data={"model": self._generation_model(), "streamed": True},
            duration_ms=(time.perf_counter() - stream_start) * 1000.0,
        )
        rag_text = text
        rag_ms = 0.0
        rag_grounding = None
        rag_hallucination = None
        rag_citation = None
        rag_agent = None
        rag_repair = None
        rag_repair_gain = 0.0
        rag_payload: dict[str, Any] | None = None
        normalized_docs = normalize_documents(retrieved_documents or [])
        normalized_citations = _normalize_citations(citations)

        citation_validation = None
        agent_validation = None
        rag_schema_ok = True
        agent_schema_ok = True
        resolved_claim_map: dict[str, str] | None = claim_map
        dependency_errors: list[str] = []
        dependency_models: list[ClaimDependency] = []

        if citations is not None:
            if not normalized_docs:
                rag_schema_ok = False
                trace.schema_validation.append(
                    {
                        "source": "citations",
                        "status": "failed",
                        "errors": ["missing_retrieved_documents"],
                    }
                )
                trace.add_step(
                    "schema_validation_failed",
                    data={"source": "citations", "reason": "missing_documents"},
                )
                normalized_citations = []
            else:
                citation_validation = validate_citations(
                    retrieved_documents=normalized_docs,
                    generated_response=rag_text,
                    citations=normalized_citations,
                    claim_map=resolved_claim_map,
                )
                resolved_claim_map = citation_validation.claim_map
                trace.schema_validation.append(
                    {
                        "source": "citations",
                        "status": "passed" if citation_validation.valid else "failed",
                        "repaired": citation_validation.repaired,
                        "error_count": len(citation_validation.errors),
                    }
                )
                if citation_validation.errors:
                    trace.add_step(
                        "schema_validation",
                        data={
                            "source": "citations",
                            "errors": [error.code for error in citation_validation.errors],
                        },
                    )
                if not citation_validation.valid:
                    rag_schema_ok = False
                normalized_citations = (
                    citation_validation.citations if citation_validation.valid else []
                )

        if agent_trace is not None:
            agent_validation = validate_agent_trace(agent_trace=agent_trace)
            trace.schema_validation.append(
                {
                    "source": "agent_trace",
                    "status": "passed" if agent_validation.valid else "failed",
                    "repaired": agent_validation.repaired,
                    "error_count": len(agent_validation.errors),
                }
            )
            if agent_validation.errors:
                trace.add_step(
                    "schema_validation",
                    data={
                        "source": "agent_trace",
                        "errors": [error.code for error in agent_validation.errors],
                    },
                )
            if not agent_validation.valid:
                agent_schema_ok = False

        if claim_dependencies:
            dependency_models = [ClaimDependency.model_validate(item) for item in claim_dependencies]
            if resolved_claim_map:
                dependency_errors = validate_dependencies(
                    claim_ids=set(resolved_claim_map.keys()),
                    dependencies=dependency_models,
                )
            if dependency_errors:
                trace.schema_validation.append(
                    {
                        "source": "claim_dependencies",
                        "status": "failed",
                        "errors": dependency_errors,
                    }
                )
                trace.add_step(
                    "schema_validation",
                    data={"source": "claim_dependencies", "errors": dependency_errors},
                )

        if normalized_docs and rag_schema_ok:
            trace.retrieval_inputs = _rag_doc_summaries(normalized_docs)
            rag_start = time.perf_counter()
            rag_grounding = self._grounding.evaluate(
                retrieved_documents=normalized_docs,
                generated_response=rag_text,
                citations=normalized_citations,
                claim_map=resolved_claim_map,
                dependencies=[item.model_dump() for item in dependency_models],
            )
            rag_hallucination = self._hallucination.evaluate(grounding=rag_grounding)
            rag_citation = self._citation_eval.evaluate(
                retrieved_documents=normalized_docs,
                citations=normalized_citations,
                grounding=rag_grounding,
                claim_map=resolved_claim_map,
            )
            if (
                rag_grounding.unsupported_claims
                or rag_hallucination.hallucinated_spans
                or rag_citation.missing_citations
            ):
                rag_repair = await self._rag_repair.repair(
                    response_text=rag_text,
                    retrieved_documents=normalized_docs,
                    grounding=rag_grounding,
                    hallucination=rag_hallucination,
                    citations=normalized_citations,
                    citation_eval=rag_citation,
                )
                if rag_repair.applied:
                    rag_text = rag_repair.repaired_text
                    updated_grounding = self._grounding.evaluate(
                        retrieved_documents=normalized_docs,
                        generated_response=rag_text,
                        citations=normalized_citations,
                        claim_map=resolved_claim_map,
                        dependencies=[item.model_dump() for item in dependency_models],
                    )
                    rag_repair_gain = (
                        updated_grounding.grounding_score - rag_grounding.grounding_score
                    )
                    rag_grounding = updated_grounding
                    rag_hallucination = self._hallucination.evaluate(grounding=rag_grounding)
                    rag_citation = self._citation_eval.evaluate(
                        retrieved_documents=normalized_docs,
                        citations=normalized_citations,
                        grounding=rag_grounding,
                        claim_map=resolved_claim_map,
                    )
            rag_ms = (time.perf_counter() - rag_start) * 1000.0
            trace.grounding = rag_grounding.model_dump()
            trace.hallucination = rag_hallucination.model_dump()
            trace.citation = rag_citation.model_dump()
            if not trace.claim_canonicalization:
                trace.claim_canonicalization = rag_grounding.canonical_claims
            if dependency_models and not trace.claim_dependencies:
                trace.claim_dependencies = [item.model_dump() for item in dependency_models]
            if rag_repair:
                trace.rag_repair = rag_repair.model_dump()
            trace.add_step(
                "rag_evaluation",
                data={
                    "grounding_score": rag_grounding.grounding_score,
                    "hallucination_score": rag_hallucination.hallucination_score,
                    "citation_accuracy": rag_citation.citation_accuracy_score,
                    "citation_precision": rag_citation.citation_precision,
                    "repair_applied": bool(rag_repair and rag_repair.applied),
                },
                duration_ms=rag_ms,
            )
        elif normalized_docs and not rag_schema_ok:
            trace.add_step(
                "rag_evaluation_skipped",
                data={"reason": "schema_validation_failed"},
            )

        if agent_trace and agent_schema_ok and agent_validation is not None:
            rag_agent = self._agent_eval.evaluate(trace=agent_validation.trace)
            trace.agent_evaluation = rag_agent.model_dump()
            trace.agent_trace = agent_validation.trace.model_dump()
            trace.add_step(
                "agent_evaluation",
                data={
                    "tool_correctness": rag_agent.tool_correctness_score,
                    "planning_score": rag_agent.planning_score,
                    "execution_alignment": rag_agent.execution_alignment_score,
                    "hallucinated_tool_usage": rag_agent.hallucinated_tool_usage,
                    "hallucinated_tool_usage_rate": rag_agent.hallucinated_tool_usage_rate,
                    "reasoning_consistency": rag_agent.reasoning_consistency_score,
                },
            )
        elif agent_trace and not agent_schema_ok:
            trace.add_step(
                "agent_evaluation_skipped",
                data={"reason": "schema_validation_failed"},
            )

        if rag_grounding or rag_agent:
            await self._memory.arecord_rag_signals(
                model=self._config.model,
                domain=domain_name,
                grounding_score=rag_grounding.grounding_score if rag_grounding else 1.0,
                hallucination_score=rag_hallucination.hallucination_score
                if rag_hallucination
                else 0.0,
                citation_accuracy=rag_citation.citation_accuracy_score if rag_citation else 1.0,
                tool_correctness=rag_agent.tool_correctness_score if rag_agent else None,
                weight=1.0,
            )
            rag_payload = {
                "grounding": rag_grounding.model_dump() if rag_grounding else None,
                "hallucination": rag_hallucination.model_dump() if rag_hallucination else None,
                "citation": rag_citation.model_dump() if rag_citation else None,
                "agent": rag_agent.model_dump() if rag_agent else None,
                "repair": rag_repair.model_dump() if rag_repair else None,
                "canonical_claims": rag_grounding.canonical_claims if rag_grounding else None,
                "claim_dependencies": [item.model_dump() for item in dependency_models]
                if dependency_models
                else None,
            }
        elif citation_validation or agent_validation:
            rag_payload = {
                "schema_validation": {
                    "citations": citation_validation.model_dump()
                    if citation_validation
                    else None,
                    "agent_trace": agent_validation.model_dump()
                    if agent_validation
                    else None,
                }
            }

        evaluation_start = time.perf_counter()
        evaluation = await self._evaluator.evaluate(
            query=query,
            response_text=rag_text,
            criteria=criteria,
            strictness_override=strictness_override,
            threshold_overrides=threshold_overrides,
            weight_overrides=weight_overrides,
        )
        evaluation_ms = (time.perf_counter() - evaluation_start) * 1000.0
        trace.evaluation = evaluation
        trace.add_step(
            "evaluation",
            data={
                "score": evaluation.weighted_score,
                "passed": evaluation.passed,
                "failed": evaluation.failed,
            },
            duration_ms=evaluation_ms,
        )
        await self._memory.arecord_evaluation(
            model=self._config.model,
            domain=domain_name,
            criteria=criteria,
            evaluation=evaluation,
            stability_score=1.0,
        )
        await self._memory.arecord_section_outcome(
            section_ids_all=[section.id for section in evaluation.sections],
            failed_section_ids=_collect_failed_sections(evaluation),
            attempt=0,
        )
        adaptation = self._memory.get_adaptation_metrics()
        decay = self._memory.get_decay_analytics(model=self._config.model, domain=domain_name)
        readiness = self._memory.get_adaptation_readiness(
            model=self._config.model, domain=domain_name
        )
        metrics = Metrics(
            provider=self._config.provider,
            model=self._config.model,
            latency_ms=0.0,
            retries=0,
            repairs=0,
            usage=Usage(),
            criteria_count=len(criteria),
            failed_criteria_count=len(evaluation.failed),
            quality_before=evaluation.weighted_score,
            quality_after=evaluation.weighted_score,
            criteria_pass_rate=evaluation.pass_rate,
            weighted_quality_score=evaluation.weighted_score,
            adaptation_strength=_adaptation_strength(adaptation),
            threshold_drift=_threshold_drift(criteria, threshold_overrides),
            decay_effect=_decay_effect(decay),
            rollback_frequency=0.0,
            memory_confidence=_evaluation_confidence(evaluation),
            adaptation_ready=readiness.get("ready", False),
            adaptation_metrics={
                "adaptation": adaptation,
                "decay": decay,
                "readiness": readiness,
            },
            grounding_score=rag_grounding.grounding_score if rag_grounding else 0.0,
            hallucination_rate=rag_hallucination.hallucination_score
            if rag_hallucination
            else 0.0,
            citation_accuracy=rag_citation.citation_accuracy_score if rag_citation else 0.0,
            citation_precision=rag_citation.citation_precision if rag_citation else 0.0,
            tool_correctness_score=rag_agent.tool_correctness_score if rag_agent else 0.0,
            agent_planning_score=rag_agent.planning_score if rag_agent else 0.0,
            execution_alignment_score=rag_agent.execution_alignment_score if rag_agent else 0.0,
            hallucinated_tool_usage_rate=rag_agent.hallucinated_tool_usage_rate if rag_agent else 0.0,
            reasoning_consistency_score=rag_agent.reasoning_consistency_score if rag_agent else 0.0,
            retrieval_alignment_score=rag_grounding.grounding_score if rag_grounding else 0.0,
            rag_repair_gain=rag_repair_gain,
        )

        trace.final_text = rag_text
        trace.outcome = "passed" if evaluation.passed else "failed"
        trace.latency_ms = (time.perf_counter() - stream_start) * 1000.0
        trace.latency_breakdown = {
            "criteria_ms": criteria_ms,
            "stream_ms": trace.latency_ms,
            "rag_ms": rag_ms,
            "evaluation_ms": evaluation_ms,
        }
        trace.memory_influence.update(
            {
                "adaptation": adaptation,
                "decay": decay,
                "readiness": readiness,
            }
        )
        trace.add_step("request_complete", data={"outcome": trace.outcome})

        yield StreamEvent(type="evaluation", data=evaluation)
        yield StreamEvent(type="metrics", data=metrics)
        yield StreamEvent(type="trace", data=trace)
        yield StreamEvent(
            type="done",
            data=GenerationResponse(
                text=rag_text,
                raw=None,
                evaluation=evaluation,
                repairs=[],
                metrics=metrics,
                trace=trace,
                rag=rag_payload,
            ),
        )

    def _messages(self, query: str) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query},
        ]

    def _generation_model(self) -> str:
        return self._config.generation_model or self._config.model


def _extract_text_and_usage(response: dict) -> tuple[str, Usage]:
    try:
        message = response["choices"][0]["message"]["content"]
    except Exception as exc:  # pragma: no cover - defensive
        raise ProviderError("Unexpected provider response shape") from exc

    usage = response.get("usage") or {}
    return (
        message,
        Usage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        ),
    )


def _extract_stream_delta(chunk: dict) -> str:
    try:
        delta = chunk["choices"][0].get("delta") or {}
        return delta.get("content") or ""
    except Exception:
        return ""


def _collect_failed_sections(evaluation: EvaluationResult) -> list[str]:
    failed_sections = {
        result.affected_section
        for result in evaluation.results
        if not result.passed and result.affected_section
    }
    return sorted(failed_sections)


def _evaluation_confidence(evaluation: EvaluationResult | None) -> float:
    if not evaluation or not evaluation.results:
        return 0.0
    total = sum(result.confidence for result in evaluation.results)
    return total / max(1, len(evaluation.results))


def _stability_score(previous: EvaluationResult, current: EvaluationResult) -> float:
    if current.weighted_score < previous.weighted_score:
        return 0.4
    if len(current.failed) < len(previous.failed):
        return 1.0
    if current.passed:
        return 0.9
    return 0.7


def _adaptation_strength(metrics: dict[str, object]) -> float:
    thresholds = metrics.get("thresholds") if isinstance(metrics, dict) else None
    if not isinstance(thresholds, dict) or not thresholds:
        return 0.0
    deltas = [
        abs(item.get("capped", 0.0) - item.get("base", 0.0))
        for item in thresholds.values()
        if isinstance(item, dict)
    ]
    return sum(deltas) / max(1, len(deltas))


def _threshold_drift(criteria: list, overrides: dict[str, float]) -> float:
    if not overrides:
        return 0.0
    base = {criterion.name: criterion.threshold for criterion in criteria}
    deltas = [abs(overrides[name] - base.get(name, overrides[name])) for name in overrides]
    return sum(deltas) / max(1, len(deltas))


def _decay_effect(decay: dict[str, object]) -> float:
    if not isinstance(decay, dict):
        return 0.0
    raw = float(decay.get("model_failed_raw", 0.0))
    decayed = float(decay.get("model_failed_decayed", 0.0))
    if raw <= 0.0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (decayed / raw)))


def _normalize_citations(
    citations: list[CitationMapping] | list[dict[str, Any]] | None,
) -> list[CitationMapping]:
    if not citations:
        return []
    normalized: list[CitationMapping] = []
    for item in citations:
        if isinstance(item, CitationMapping):
            normalized.append(item)
        elif isinstance(item, dict):
            try:
                normalized.append(CitationMapping.model_validate(item))
            except Exception:
                continue
    return normalized


def _rag_doc_summaries(documents: list) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for doc in documents:
        text = doc.text or ""
        summaries.append(
            {
                "id": doc.id,
                "source": doc.source,
                "score": doc.score,
                "length": len(text),
                "preview": text[:160],
            }
        )
    return summaries
