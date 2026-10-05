export type AnalysisValue =
  | string
  | number
  | boolean
  | null
  | AnalysisValue[]
  | { [key: string]: AnalysisValue };

export interface AnalysisTable {
  grain: string;
  columns: string[];
  row_count: number;
  metric_definitions: Record<string, string>;
  rows: Array<Record<string, AnalysisValue>>;
}

export interface AnalysisObservation {
  id: string;
  text_markdown: string;
  evidence_tables: string[];
}

export interface AnalysisQuestion {
  id: string;
  title: string;
  status: string;
  method_and_definitions_markdown: string;
  population_and_denominators: string;
  limitations_markdown: string;
  metrics: Record<string, AnalysisValue>;
  observations: AnalysisObservation[];
  tables: Record<string, AnalysisTable>;
}

export interface AnalysisSummary {
  repositories: number;
  finding_records: number;
  component_records: number;
  questions: number;
  scope: string;
}

export interface AnalysisConventions {
  null: string;
  proportions: string;
  statuses: Record<string, string>;
  tools: string;
}

export interface Analysis {
  schema_version: string;
  generated_at_utc: string;
  organization: string;
  clone_run: string;
  summary: AnalysisSummary;
  conventions: AnalysisConventions;
  provenance: Record<string, AnalysisValue>;
  coverage: Record<string, AnalysisTable>;
  questions: AnalysisQuestion[];
}
