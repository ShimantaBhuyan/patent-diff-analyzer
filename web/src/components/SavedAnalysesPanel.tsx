'use client';

import { SavedAnalysisSummary } from '@/types';

interface SavedAnalysesPanelProps {
  analyses: SavedAnalysisSummary[];
  visible: boolean;
  onToggle: () => void;
  onLoad: (jobId: string) => void;
  onRefresh: () => void;
}

export default function SavedAnalysesPanel({
  analyses,
  visible,
  onToggle,
  onLoad,
  onRefresh,
}: SavedAnalysesPanelProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900">Saved Analyses</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
            title="Refresh"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button
            onClick={onToggle}
            className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors lg:hidden"
          >
            <svg className={`w-4 h-4 transition-transform ${visible ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      <div className={`${visible ? 'block' : 'hidden lg:block'}`}>
        {analyses.length === 0 ? (
          <div className="p-6 text-center">
            <svg className="w-10 h-10 text-gray-300 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
            <p className="text-sm text-gray-500">No saved analyses yet.</p>
            <p className="text-xs text-gray-400 mt-1">Run and save an analysis to see it here.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
            {analyses.map((item) => (
              <button
                key={item.job_id}
                onClick={() => onLoad(item.job_id)}
                className="w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors"
              >
                <p className="text-sm font-medium text-gray-900 truncate">{item.saved_name}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
                    item.status === 'completed'
                      ? 'bg-green-100 text-green-800'
                      : item.status === 'failed'
                      ? 'bg-red-100 text-red-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}>
                    {item.status}
                  </span>
                  <span className="text-xs text-gray-400">
                    {new Date(item.saved_at).toLocaleDateString()}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
