'use client';

import { useState, useEffect, useCallback } from 'react';
import DocumentUploader from '@/components/DocumentUploader';
import AnalysisPanel from '@/components/AnalysisPanel';
import SavedAnalysesPanel from '@/components/SavedAnalysesPanel';
import { AnalysisResponse, Document, SavedAnalysisSummary } from '@/types';

export default function Home() {
  const [patentA, setPatentA] = useState<Document | null>(null);
  const [patentB, setPatentB] = useState<Document | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string>('');
  const [savedAnalyses, setSavedAnalyses] = useState<SavedAnalysisSummary[]>([]);
  const [showSaved, setShowSaved] = useState(false);

  const loadSaved = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/analysis/saved/list');
      if (res.ok) {
        const data = await res.json();
        setSavedAnalyses(data);
      }
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    loadSaved();
  }, [loadSaved]);

  const handleUploadA = (doc: Document) => {
    setPatentA(doc);
    setError('');
  };

  const handleUploadB = (doc: Document) => {
    setPatentB(doc);
    setError('');
  };

  const runAnalysis = async () => {
    if (!patentA || !patentB) {
      setError('Please upload both Patent A and Patent B');
      return;
    }

    setIsAnalyzing(true);
    setError('');

    try {
      const response = await fetch('http://localhost:8000/api/v1/analysis/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patent_a_id: patentA.document_id,
          patent_b_id: patentB.document_id,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Analysis failed');
      }

      const data: AnalysisResponse = await response.json();
      setAnalysis(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Analysis failed';
      setError(message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const runAudit = async () => {
    if (!analysis?.job_id) return;

    setIsAnalyzing(true);
    setError('');

    try {
      const response = await fetch(`http://localhost:8000/api/v1/audit/${analysis.job_id}`, {
        method: 'POST',
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Audit failed');
      }

      const data: AnalysisResponse = await response.json();
      setAnalysis(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Audit failed';
      setError(message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const loadAnalysis = async (jobId: string) => {
    setIsAnalyzing(true);
    setError('');
    try {
      const res = await fetch(`http://localhost:8000/api/v1/analysis/${jobId}`);
      if (!res.ok) throw new Error('Failed to load analysis');
      const data: AnalysisResponse = await res.json();
      setAnalysis(data);
      setPatentA(null);
      setPatentB(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load analysis';
      setError(message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const bothUploaded = !!patentA && !!patentB;
  const hasAnalysis = !!analysis;

  return (
    <main className="min-h-screen">
      {/* Header — full width */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-orange-600 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-gray-900">Patent Diff Analyzer</h1>
          </div>

          <div className="flex items-center gap-3">
            {hasAnalysis && (
              <button
                onClick={() => {
                  setAnalysis(null);
                  setPatentA(null);
                  setPatentB(null);
                  setError('');
                }}
                className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
              >
                Analyze New PDF
              </button>
            )}
            {/* {!hasAnalysis && (
              <button
                onClick={() => setShowSaved(!showSaved)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  showSaved
                    ? 'bg-gray-800 text-white'
                    : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Saved Analyses
              </button>
            )} */}

            {analysis?.status === 'completed' && (
              <button
                onClick={runAudit}
                disabled={isAnalyzing}
                className="px-4 py-2 bg-gray-800 text-white rounded-lg font-medium hover:bg-gray-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isAnalyzing ? 'Auditing...' : 'Audit Analysis'}
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Upload / Home Section */}
      {!analysis && (
        <div className="px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Uploaders */}
            <div className="lg:col-span-2">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <DocumentUploader
                  label="Patent A"
                  document={patentA}
                  onUpload={handleUploadA}
                  onRemove={() => setPatentA(null)}
                />
                <DocumentUploader
                  label="Patent B"
                  document={patentB}
                  onUpload={handleUploadB}
                  onRemove={() => setPatentB(null)}
                />
              </div>

              {bothUploaded && !hasAnalysis && (
                <div className="mt-6 flex flex-col items-center gap-2">
                  <button
                    onClick={runAnalysis}
                    disabled={isAnalyzing}
                    className="px-6 py-2.5 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isAnalyzing ? 'Analyzing...' : 'Run Analysis'}
                  </button>
                  <span className="text-xs text-gray-500 max-w-xs truncate" title={`${patentA?.title || 'Patent A'} vs ${patentB?.title || 'Patent B'}`}>
                    {patentA?.title || 'Patent A'} vs {patentB?.title || 'Patent B'}
                  </span>
                </div>
              )}

              {error && (
                <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                  {error}
                </div>
              )}

              {/* Analysis progress */}
              {isAnalyzing && (
                <div className="mt-8 p-8 bg-white border border-gray-200 rounded-xl text-center">
                  <div className="mx-auto w-12 h-12 border-4 border-orange-200 border-t-orange-600 rounded-full animate-spin mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-1">Analyzing Patents</h3>
                  <p className="text-sm text-gray-500">
                    This may take a minute while we extract claims, run retrieval, and generate the diff report.
                  </p>
                </div>
              )}
            </div>

            {/* Saved Analyses Sidebar */}
            <div className="lg:col-span-1">
              <SavedAnalysesPanel
                analyses={savedAnalyses}
                visible={showSaved}
                onToggle={() => setShowSaved(!showSaved)}
                onLoad={loadAnalysis}
                onRefresh={loadSaved}
              />
            </div>
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {analysis && (
        <AnalysisPanel
          analysis={analysis}
          onReset={() => {
            setAnalysis(null);
            setPatentA(null);
            setPatentB(null);
            setError('');
          }}
          onSaveChange={loadSaved}
        />
      )}
    </main>
  );
}
