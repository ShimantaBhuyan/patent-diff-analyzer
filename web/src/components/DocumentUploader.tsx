'use client';

import { useState } from 'react';
import { Document } from '@/types';

interface DocumentUploaderProps {
  label: string;
  document: Document | null;
  onUpload: (doc: Document) => void;
  onRemove: () => void;
}

export default function DocumentUploader({ label, document, onUpload, onRemove }: DocumentUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState('');

  const handleUpload = async (file: File) => {
    if (!file.name.endsWith('.pdf') && !file.name.endsWith('.txt')) {
      setError('Please upload a PDF or text file');
      return;
    }

    setIsUploading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/documents/upload?label=${encodeURIComponent(label)}`,
        {
          method: 'POST',
          body: formData,
        }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data: Document = await response.json();
      onUpload(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
    } finally {
      setIsUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  if (document) {
    const hasWarnings = document.parse_warnings && document.parse_warnings.length > 0;
    return (
      <div className={`p-6 border-2 rounded-xl ${hasWarnings ? 'bg-yellow-50 border-yellow-200' : 'bg-green-50 border-green-200'}`}>
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${hasWarnings ? 'bg-yellow-100' : 'bg-green-100'}`}>
            <svg className={`w-5 h-5 ${hasWarnings ? 'text-yellow-600' : 'text-green-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {hasWarnings ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              )}
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <p className={`font-medium ${hasWarnings ? 'text-yellow-900' : 'text-green-900'}`}>{document.title || label}</p>
            <p className={`text-sm truncate ${hasWarnings ? 'text-yellow-700' : 'text-green-700'}`}>{document.filename}</p>
          </div>
          <button
            onClick={onRemove}
            className="px-3 py-1.5 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Replace
          </button>
        </div>
        {hasWarnings && (
          <div className="mt-3 p-3 bg-yellow-100/50 rounded-lg">
            <p className="text-sm font-medium text-yellow-800 mb-1">Warnings:</p>
            <ul className="list-disc list-inside text-sm text-yellow-700 space-y-0.5">
              {document.parse_warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      className={`p-8 border-2 border-dashed rounded-xl transition-colors ${
        isDragging
          ? 'border-orange-400 bg-orange-50'
          : 'border-gray-300 bg-white hover:border-gray-400'
      }`}
    >
      <div className="text-center">
        <div className="mx-auto w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        </div>
        <p className="text-lg font-medium text-gray-900 mb-1">{label}</p>
        <p className="text-sm text-gray-500 mb-4">
          Drag and drop a PDF or text file, or click to browse
        </p>
        <input
          type="file"
          accept=".pdf,.txt"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUpload(file);
          }}
          className="hidden"
          id={`file-input-${label.replace(/\s+/g, '-')}`}
        />
        <label
          htmlFor={`file-input-${label.replace(/\s+/g, '-')}`}
          className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50 cursor-pointer transition-colors"
        >
          {isUploading ? 'Uploading...' : 'Browse Files'}
        </label>
      </div>

      {error && (
        <p className="mt-4 text-sm text-red-600 text-center">{error}</p>
      )}
    </div>
  );
}
