import * as echarts from "echarts/core";
import type {
    BarSeriesOption,
    BoxplotSeriesOption,
    HeatmapSeriesOption,
    LineSeriesOption,
    PieSeriesOption,
    ScatterSeriesOption,
} from "echarts/charts";
import {BarChart, BoxplotChart, HeatmapChart, LineChart, PieChart, ScatterChart,} from "echarts/charts";
import type {
    DatasetComponentOption,
    GridComponentOption,
    LegendComponentOption,
    TitleComponentOption,
    TooltipComponentOption,
    VisualMapComponentOption,
} from "echarts/components";
import {
    DatasetComponent,
    GridComponent,
    LegendComponent,
    TitleComponent,
    TooltipComponent,
    VisualMapComponent,
} from "echarts/components";
import {CanvasRenderer} from "echarts/renderers";

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  BoxplotChart,
  ScatterChart,
  HeatmapChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export type EChartsOption = echarts.ComposeOption<
  | LineSeriesOption
  | BarSeriesOption
  | PieSeriesOption
  | BoxplotSeriesOption
  | ScatterSeriesOption
  | HeatmapSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | TitleComponentOption
  | DatasetComponentOption
  | VisualMapComponentOption
>;

export * from "echarts/core";
