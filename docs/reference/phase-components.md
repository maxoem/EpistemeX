# Phase Component Reference

Injected extractors, linkers, rerankers, and classifiers used across Phases 2–4. As injected computational
units they are recursively discovered by `find_components` and their state is fingerprinted for run invalidation
and phase reuse.

## Entity Linkers & NER (Phase 2)

### DenseEntityLinker

Dense retrieval based entity linker.

::: episteme_pipeline.phases.phase2_entity_discovery.sota_entity_linker.DenseEntityLinker
    options:
      show_root_heading: false
      show_root_toc_entry: false

### JevEntityLinker

::: episteme_pipeline.phases.phase2_entity_discovery.jev_entity_linker.JevEntityLinker
    options:
      show_root_heading: false
      show_root_toc_entry: false

### CascadingEntityLinker

::: episteme_pipeline.phases.phase2_entity_discovery.jev_entity_linker.CascadingEntityLinker
    options:
      show_root_heading: false
      show_root_toc_entry: false

### LLMNERExtractor

::: episteme_pipeline.phases.phase2_entity_discovery.ner_extractor.LLMNERExtractor
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Rerankers & Global Relation Extractors (Phase 3)

### DenseRetrievalGlobalRelationExtractor

::: episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor.DenseRetrievalGlobalRelationExtractor
    options:
      show_root_heading: false
      show_root_toc_entry: false

### JevRelationReranker

::: episteme_pipeline.phases.phase3_global_relations.rerankers.JevRelationReranker
    options:
      show_root_heading: false
      show_root_toc_entry: false

### CrossEncoderRelationReranker

::: episteme_pipeline.phases.phase3_global_relations.rerankers.CrossEncoderRelationReranker
    options:
      show_root_heading: false
      show_root_toc_entry: false

### SentenceTransformerCrossEncoderReranker

::: episteme_pipeline.phases.phase3_global_relations.rerankers.SentenceTransformerCrossEncoderReranker
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Argument Classifiers (Phase 4)

### LLMACCClassifier

Anti-contribution claim (ACC) classifier.

::: episteme_pipeline.phases.phase4_argument_mining.acc_classifier.LLMACCClassifier
    options:
      show_root_heading: false
      show_root_toc_entry: false

### TAGARCClassifier

Anti-research claim (ARC) classifier.

::: episteme_pipeline.phases.phase4_argument_mining.arc_classifier.TAGARCClassifier
    options:
      show_root_heading: false
      show_root_toc_entry: false
