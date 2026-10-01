import React, { useMemo } from "react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { BenchmarkRegistryTable } from "./BenchmarkRegistryTable";
import { BenchmarkDetailView } from "./BenchmarkDetailView";
import type { BenchmarkDescriptor } from "../../../api/types";

interface BenchmarkCatalogPageProps {
  onSelectRunToEvaluate?: (benchmarkId: string) => void;
}

export const BenchmarkCatalogPage: React.FC<BenchmarkCatalogPageProps> = ({
  onSelectRunToEvaluate,
}) => {
  const {
    benchmarks,
    selectedBenchmarkId,
    setSelectedBenchmarkId,
    setActiveMode,
    catalogViewMode,
    setCatalogViewMode,
    setIsPromoteModalOpen,
    setIsRegisterModalOpen,
  } = useEvaluationStore();

  // Active selected benchmark
  const activeBenchmark: BenchmarkDescriptor | undefined = useMemo(() => {
    if (!benchmarks.length) return undefined;
    if (!selectedBenchmarkId) return benchmarks[0];
    return benchmarks.find((b) => b.id === selectedBenchmarkId) || benchmarks[0];
  }, [benchmarks, selectedBenchmarkId]);

  const handleSelectBenchmark = (id: string) => {
    setSelectedBenchmarkId(id);
  };

  const handleInspectBenchmark = (id: string) => {
    setSelectedBenchmarkId(id);
    setCatalogViewMode("detail");
  };

  const handleEvaluateBenchmark = (benchmark: BenchmarkDescriptor) => {
    setSelectedBenchmarkId(benchmark.id);
    if (onSelectRunToEvaluate) {
      onSelectRunToEvaluate(benchmark.id);
    } else {
      setActiveMode("execute");
    }
  };

  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-app-bg text-app-text font-sans">
      {catalogViewMode === "table" ? (
        <BenchmarkRegistryTable
          benchmarks={benchmarks}
          selectedBenchmarkId={selectedBenchmarkId || (benchmarks[0]?.id ?? null)}
          onSelectBenchmark={handleSelectBenchmark}
          onInspectBenchmark={handleInspectBenchmark}
          onEvaluateBenchmark={handleEvaluateBenchmark}
          onRegisterClick={() => setIsRegisterModalOpen(true)}
          onPromoteClick={() => setIsPromoteModalOpen(true)}
        />
      ) : activeBenchmark ? (
        <BenchmarkDetailView
          benchmark={activeBenchmark}
          onBackToRegistry={() => setCatalogViewMode("table")}
          onEvaluateBenchmark={handleEvaluateBenchmark}
          onPromoteClick={() => setIsPromoteModalOpen(true)}
        />
      ) : (
        <BenchmarkRegistryTable
          benchmarks={benchmarks}
          selectedBenchmarkId={null}
          onSelectBenchmark={handleSelectBenchmark}
          onInspectBenchmark={handleInspectBenchmark}
          onEvaluateBenchmark={handleEvaluateBenchmark}
          onRegisterClick={() => setIsRegisterModalOpen(true)}
          onPromoteClick={() => setIsPromoteModalOpen(true)}
        />
      )}
    </div>
  );
};
