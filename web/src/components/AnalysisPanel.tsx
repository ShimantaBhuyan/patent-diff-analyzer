'use client';

import { useState } from 'react';
import { AnalysisResponse, ClaimSummary } from '@/types';

interface AnalysisPanelProps {
  analysis: AnalysisResponse;
  onReset: () => void;
  onSaveChange?: () => void;
}

export default function AnalysisPanel({ analysis, onReset, onSaveChange }: AnalysisPanelProps) {
  const [selectedClaim, setSelectedClaim] = useState<string | null>(null);
  const [showAudit, setShowAudit] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveError, setSaveError] = useState('');
  const [justSaved, setJustSaved] = useState(false);

  const results = analysis.results || [];
  const findings = analysis.audit_findings || [];

  const selectedResult = results.find(r => r.claim_id === selectedClaim);

  const patentATitle = analysis.patent_a_title || 'Patent A';
  const patentBTitle = analysis.patent_b_title || 'Patent B';

  const patentAClaimsMap = new Map<string, ClaimSummary>();
  for (const c of analysis.patent_a_claims) {
    patentAClaimsMap.set(c.claim_id, c);
  }
  const patentBClaimsMap = new Map<string, ClaimSummary>();
  for (const c of analysis.patent_b_claims) {
    patentBClaimsMap.set(c.claim_id, c);
  }

  // Helper: extract claim number from a claim_id like "uuid#C10" -> "10"
  const getClaimNumber = (claimId: string): string => {
    const match = claimId.match(/#C(\d+)$/);
    return match ? match[1] : claimId;
  };

  // Helper: check if a Patent B claim is matched by any entry in matched_claims
  const isClaimMatched = (claimId: string, matchedClaims: string[]): boolean => {
    const claimNum = getClaimNumber(claimId);
    return matchedClaims.some(m => {
      // Exact match
      if (m === claimId) return true;
      // The LLM sometimes returns just the claim number or "claim N"
      const mNum = m.replace(/\D/g, '');
      return mNum === claimNum;
    });
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'high': return 'bg-red-100 text-red-800 border-red-200';
      case 'medium': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'low': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getConfidenceColor = (confidence: string) => {
    switch (confidence) {
      case 'high': return 'bg-green-100 text-green-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'low': return 'bg-orange-100 text-orange-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'error': return 'bg-red-100 text-red-800 border-red-200';
      case 'warning': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-blue-100 text-blue-800 border-blue-200';
    }
  };

  const handleSave = async () => {
    setSaveError('');
    const name = saveName.trim() || `Analysis ${new Date().toLocaleString()}`;
    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/analysis/${analysis.job_id}/save?name=${encodeURIComponent(name)}`,
        { method: 'POST' }
      );
      if (!res.ok) throw new Error('Save failed');
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2000);
      onSaveChange?.();
    } catch {
      setSaveError('Failed to save analysis');
    }
  };

  const handleUnsave = async () => {
    setSaveError('');
    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/analysis/${analysis.job_id}/save`,
        { method: 'DELETE' }
      );
      if (!res.ok) throw new Error('Unsave failed');
      onSaveChange?.();
    } catch {
      setSaveError('Failed to remove save');
    }
  };

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col">
      {/* Toolbar */}
      <div className="bg-white border-b border-gray-200 px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500">
            Status: <span className="font-medium text-gray-900 capitalize">{analysis.status}</span>
          </span>
          {analysis.completed_at && (
            <span className="text-sm text-gray-500 hidden sm:inline">
              Completed: {new Date(analysis.completed_at).toLocaleString()}
            </span>
          )}
          {findings.length > 0 && (
            <button
              onClick={() => setShowAudit(true)}
              className="text-sm font-medium px-3 py-1 rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
            >
              Audit ({findings.length} findings)
            </button>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Save controls */}
          <div className="hidden sm:flex items-center gap-2">
            {analysis.saved_name ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Saved as <span className="font-medium">{analysis.saved_name}</span></span>
                <button
                  onClick={handleUnsave}
                  className="text-xs text-red-600 hover:text-red-700 underline"
                >
                  Remove
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  placeholder="Name this analysis..."
                  className="text-sm px-2 py-1 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500 w-40"
                />
                <button
                  onClick={handleSave}
                  className={`text-sm px-3 py-1.5 rounded-md font-medium transition-colors ${
                    justSaved
                      ? 'bg-green-600 text-white'
                      : 'bg-orange-600 text-white hover:bg-orange-700'
                  }`}
                >
                  {justSaved ? 'Saved!' : 'Save'}
                </button>
              </div>
            )}
            {saveError && <span className="text-xs text-red-600">{saveError}</span>}
          </div>

          <button
            onClick={onReset}
            className="sm:hidden text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            New
          </button>
        </div>
      </div>

      {/* Mobile Save Bar */}
      {!analysis.saved_name && (
        <div className="sm:hidden bg-gray-50 border-b border-gray-200 px-4 py-2 flex items-center gap-2">
          <input
            type="text"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="Name this analysis..."
            className="flex-1 text-sm px-2 py-1 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
          />
          <button
            onClick={handleSave}
            className={`text-sm px-3 py-1.5 rounded-md font-medium transition-colors ${
              justSaved ? 'bg-green-600 text-white' : 'bg-orange-600 text-white'
            }`}
          >
            {justSaved ? 'Saved!' : 'Save'}
          </button>
        </div>
      )}

      {/* Audit Drawer */}
      {showAudit && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-sm"
            onClick={() => setShowAudit(false)}
          />
          <div className="relative w-full max-w-lg bg-white shadow-2xl h-full flex flex-col animate-slideInRight">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Audit Findings</h2>
                <p className="text-sm text-gray-500">{findings.length} issue{findings.length !== 1 ? 's' : ''} found</p>
              </div>
              <button
                onClick={() => setShowAudit(false)}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
              {findings.map((finding, idx) => (
                <div key={idx} className={`p-3 rounded-lg border text-sm ${getSeverityColor(finding.severity)}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium capitalize">{finding.severity}</span>
                    <span className="text-gray-600">•</span>
                    <span className="font-mono text-xs">{finding.claim_id}</span>
                    <span className="text-gray-600">•</span>
                    <span className="capitalize">{finding.finding_type.replace(/_/g, ' ')}</span>
                  </div>
                  <p className="text-gray-700">{finding.message}</p>
                  {finding.suggested_action && (
                    <p className="text-gray-600 mt-1 text-xs">Suggested: {finding.suggested_action}</p>
                  )}
                </div>
              ))}
            </div>

            <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
              <button
                onClick={() => setShowAudit(false)}
                className="w-full px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Three-Panel Layout */}
      <div className="flex-1 grid grid-cols-12 gap-0 overflow-hidden">
        {/* Left Panel: Patent A Claims */}
        <div className="col-span-3 border-r border-gray-200 bg-white overflow-y-auto">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-sm font-semibold text-gray-900 truncate" title={patentATitle}>{patentATitle}</h2>
            <p className="text-xs text-gray-500 mt-1">{results.length} claims analyzed</p>
          </div>
          <div className="divide-y divide-gray-100">
            {results.map((result) => (
              <button
                key={result.claim_id}
                onClick={() => setSelectedClaim(result.claim_id)}
                className={`w-full text-left p-4 transition-colors ${
                  selectedClaim === result.claim_id
                    ? 'bg-orange-50 border-l-4 border-orange-500'
                    : 'hover:bg-gray-50 border-l-4 border-transparent'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono text-gray-500">{result.claim_id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getRiskColor(result.risk)}`}>
                    {result.risk}
                  </span>
                </div>
                <p className="text-sm text-gray-700 line-clamp-3">
                  {result.overlap || 'No overlap analysis available'}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${getConfidenceColor(result.confidence)}`}>
                    {result.confidence.replace('_', ' ')}
                  </span>
                  {result.citations.length > 0 && (
                    <span className="text-xs text-gray-500">
                      {result.citations.length} citation{result.citations.length !== 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Center Panel: Diff View */}
        <div className="col-span-6 bg-gray-50 overflow-y-auto">
          {selectedResult ? (
            <div className="p-6 space-y-6">
              {/* Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{selectedResult.claim_id}</h2>
                  <p className="text-sm text-gray-500 truncate max-w-md" title={patentATitle}>{patentATitle}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${getRiskColor(selectedResult.risk)}`}>
                    Risk: {selectedResult.risk}
                  </span>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${getConfidenceColor(selectedResult.confidence)}`}>
                    {selectedResult.confidence.replace('_', ' ')}
                  </span>
                </div>
              </div>

              {/* Claim Text */}
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Claim Text
                </h3>
                <p className="text-sm text-gray-700 italic">
                  {patentAClaimsMap.get(selectedResult.claim_id)?.text || 'Claim text not available'}
                </p>
              </div>

              {/* Overlap */}
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <svg className="w-4 h-4 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Overlap
                </h3>
                <p className="text-sm text-gray-700">{selectedResult.overlap}</p>
              </div>

              {/* Differences */}
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                  Differences
                </h3>
                <p className="text-sm text-gray-700">{selectedResult.differences}</p>
              </div>

              {/* Novelty */}
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <svg className="w-4 h-4 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Novelty Assessment
                </h3>
                <p className="text-sm text-gray-700">{selectedResult.novelty}</p>
              </div>

              {/* Citations - Evidence First */}
              {selectedResult.citations.length > 0 && (
                <div className="bg-white rounded-lg border border-gray-200 p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Evidence ({selectedResult.citations.length} citations)
                  </h3>
                  <div className="space-y-3">
                    {selectedResult.citations.map((citation, idx) => (
                      <div key={idx} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-mono text-gray-500">{citation.chunk_id}</span>
                          <span className="text-xs text-gray-400">•</span>
                          <span className="text-xs text-gray-500">{citation.section || 'unknown section'}</span>
                        </div>
                        <blockquote className="text-sm text-gray-700 italic border-l-2 border-orange-300 pl-3">
                          &ldquo;{citation.exact_quote}&rdquo;
                        </blockquote>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Reasoning */}
              {selectedResult.reasoning && (
                <div className="bg-white rounded-lg border border-gray-200 p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                    <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    Reasoning
                  </h3>
                  <p className="text-sm text-gray-700">{selectedResult.reasoning}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <svg className="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-gray-500">Select a claim from {patentATitle} to view analysis</p>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel: All Patent B Claims */}
        <div className="col-span-3 border-l border-gray-200 bg-white overflow-y-auto">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-sm font-semibold text-gray-900 truncate" title={patentBTitle}>{patentBTitle}</h2>
            <p className="text-xs text-gray-500 mt-1">
              {analysis.patent_b_claims.length} claims found
            </p>
          </div>

          {selectedResult ? (
            <div className="divide-y divide-gray-100">
              {analysis.patent_b_claims.map((claim) => {
                const isMatched = isClaimMatched(claim.claim_id, selectedResult.matched_claims);
                return (
                  <div
                    key={claim.claim_id}
                    className={`p-4 transition-colors ${isMatched ? 'bg-orange-50' : 'hover:bg-gray-50'}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-mono text-gray-500">{claim.claim_id}</span>
                      {isMatched && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-800 font-medium">
                          Matched
                        </span>
                      )}
                    </div>
                    <p className={`text-sm ${isMatched ? 'text-gray-900' : 'text-gray-600'}`}>
                      {claim.text}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-8 text-center">
              <p className="text-sm text-gray-400">
                Select a claim to see {patentBTitle} claims
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
