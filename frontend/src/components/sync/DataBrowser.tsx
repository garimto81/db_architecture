/**
 * DataBrowser - NAS 폴더 트리 및 파일 브라우저
 * BLOCK_FRONTEND / FrontendAgent
 * Issue #23: 동기화된 폴더 트리 구조 및 파일 구조 표시
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Badge } from '../common';
import { apiClient } from '../../services/api';
import type { FolderNode, FolderTreeResponse } from '../../types/sync';

// API 호출 함수
async function fetchFolderTree(projectCode?: string): Promise<FolderTreeResponse> {
  const params = new URLSearchParams();
  if (projectCode) params.set('project_code', projectCode);
  params.set('max_depth', '5');

  const response = await apiClient.get<FolderTreeResponse>(`/api/sync/tree?${params}`);
  return response.data;
}

// 파일 크기 포맷
function formatFileSize(bytes?: number): string {
  if (!bytes) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

// 트리 노드 컴포넌트
function TreeNode({
  node,
  depth = 0,
  onSelect,
  selectedPath,
}: {
  node: FolderNode;
  depth?: number;
  onSelect: (node: FolderNode) => void;
  selectedPath?: string;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const isFolder = node.type === 'folder';
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = node.path === selectedPath;

  const handleClick = () => {
    if (isFolder && hasChildren) {
      setExpanded(!expanded);
    }
    onSelect(node);
  };

  return (
    <div>
      <div
        className={`flex items-center gap-2 py-1 px-2 cursor-pointer rounded hover:bg-gray-100 ${
          isSelected ? 'bg-blue-50 text-blue-700' : ''
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={handleClick}
      >
        {/* 확장/축소 아이콘 */}
        {isFolder && hasChildren ? (
          <span className="w-4 text-gray-400">{expanded ? '▼' : '▶'}</span>
        ) : (
          <span className="w-4" />
        )}

        {/* 폴더/파일 아이콘 */}
        <span>{isFolder ? '📁' : '🎬'}</span>

        {/* 이름 */}
        <span className="truncate flex-1 text-sm">{node.name}</span>

        {/* 메타데이터 */}
        {isFolder && node.metadata?.file_count !== undefined && (
          <span className="text-xs text-gray-400">
            {node.metadata.file_count}개
          </span>
        )}
        {!isFolder && node.metadata?.size_bytes && (
          <span className="text-xs text-gray-400">
            {formatFileSize(node.metadata.size_bytes)}
          </span>
        )}
      </div>

      {/* 자식 노드 */}
      {expanded && hasChildren && (
        <div>
          {node.children!.map((child, idx) => (
            <TreeNode
              key={`${child.name}-${idx}`}
              node={child}
              depth={depth + 1}
              onSelect={onSelect}
              selectedPath={selectedPath}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// 파일 메타데이터 패널
function FileMetadataPanel({ node }: { node: FolderNode | null }) {
  if (!node || node.type === 'folder') {
    return (
      <div className="text-center text-gray-400 py-8">
        파일을 선택하면 상세 정보가 표시됩니다.
      </div>
    );
  }

  const metadata = node.metadata || {};

  return (
    <div className="space-y-3">
      <h4 className="font-medium text-gray-900 truncate">{node.name}</h4>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="text-gray-500">경로</div>
        <div className="truncate text-gray-700" title={node.path}>
          {node.path}
        </div>

        <div className="text-gray-500">크기</div>
        <div className="text-gray-700">{formatFileSize(metadata.size_bytes)}</div>

        {metadata.version_type && (
          <>
            <div className="text-gray-500">버전</div>
            <div>
              <Badge
                status={
                  metadata.version_type === 'clean'
                    ? 'idle'
                    : metadata.version_type === 'stream'
                    ? 'running'
                    : 'idle'
                }
                label={metadata.version_type}
              />
            </div>
          </>
        )}

        {metadata.display_title && (
          <>
            <div className="text-gray-500">제목</div>
            <div className="text-gray-700">{metadata.display_title}</div>
          </>
        )}
      </div>
    </div>
  );
}

// 메인 컴포넌트
export function DataBrowser() {
  const [selectedNode, setSelectedNode] = useState<FolderNode | null>(null);
  const [projectFilter, setProjectFilter] = useState<string>('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['folderTree', projectFilter],
    queryFn: () => fetchFolderTree(projectFilter || undefined),
    staleTime: 5 * 60 * 1000, // 5분 캐시
  });

  const projects = ['', 'WSOP', 'GGMILLIONS', 'MPP', 'PAD', 'GOG', 'HCL'];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* 폴더 트리 패널 */}
      <Card title="📂 폴더 구조" className="lg:col-span-2">
        {/* 프로젝트 필터 */}
        <div className="mb-4">
          <select
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {projects.map((p) => (
              <option key={p} value={p}>
                {p || '전체 프로젝트'}
              </option>
            ))}
          </select>
        </div>

        {/* 통계 */}
        {data && (
          <div className="flex gap-4 mb-4 text-sm text-gray-500">
            <span>📁 {data.total_folders.toLocaleString()}개 폴더</span>
            <span>🎬 {data.total_files.toLocaleString()}개 파일</span>
          </div>
        )}

        {/* 트리 뷰 */}
        <div className="max-h-96 overflow-y-auto border rounded-lg">
          {isLoading ? (
            <div className="p-4 text-center text-gray-500">로딩 중...</div>
          ) : error ? (
            <div className="p-4 text-center text-red-500">
              데이터를 불러오는 중 오류가 발생했습니다.
            </div>
          ) : data?.projects && data.projects.length > 0 ? (
            data.projects.map((project, idx) => (
              <TreeNode
                key={`${project.name}-${idx}`}
                node={project}
                onSelect={setSelectedNode}
                selectedPath={selectedNode?.path}
              />
            ))
          ) : (
            <div className="p-4 text-center text-gray-500">
              동기화된 파일이 없습니다.
            </div>
          )}
        </div>
      </Card>

      {/* 메타데이터 패널 */}
      <Card title="📄 파일 정보">
        <FileMetadataPanel node={selectedNode} />
      </Card>
    </div>
  );
}
