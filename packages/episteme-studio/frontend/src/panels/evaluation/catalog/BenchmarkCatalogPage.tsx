import React, { useState, useMemo } from "react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { BenchmarkRegistryTable } from "./BenchmarkRegistryTable";
import { BenchmarkDetailView } from "./BenchmarkDetailView";
import { PromoteToGoldModal } from "./PromoteToGoldModal";
import { RegisterBenchmarkModal } from "./RegisterBenchmarkModal";
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
  } = useEvaluationStore();

  const [viewMode, setViewMode] = useState<"table" | "detail">("table");
  const [isPromoteModalOpen, setIsPromoteModalOpen] = useState(false);
  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);

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
    setViewMode("detail");
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
      {viewMode === "table" ? (
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
          onBackToRegistry={() => setViewMode("table")}
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

      {/* Auxiliary Modals */}
      <PromoteToGoldModal
        isOpen={isPromoteModalOpen}
        onClose={() => setIsPromoteModalOpen(false)}
      />

      <RegisterBenchmarkModal
        isOpen={isRegisterModalOpen}
        onClose={() => setIsRegisterModalOpen(false)}
      />
    </div>
  );
};
