"use client";

import { Copy, Check } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";

interface TraceStep {
  step: string;
  [key: string]: any;
}

interface TraceChainProps {
  trace: TraceStep[];
  live: boolean;
}

// ---------------------------------------------------------------------------
// Tree-building — transforms the flat trace array into a nested structure.
//
// Main Agent trace entries (research, research_result, draft, draft_result,
// finalize) merge into the current Main Agent block (level 0).
// tool_result  → level-2 child of the current Researcher (label = entry.tool)
// research     → opens a Researcher block (level 1 child of Main Agent)
// draft        → opens a Writer block (level 1 child of Main Agent)
// quality_check → standalone level-0 root that closes the current Main Agent
// ---------------------------------------------------------------------------

interface TreeNode {
  id: string;
  label: string;
  level: 0 | 1 | 2;
  detail?: TraceStep;
  children: TreeNode[];
}

function buildTree(trace: TraceStep[]): TreeNode[] {
  const roots: TreeNode[] = [];
  let currentMain: TreeNode | null = null;
  let currentResearcher: TreeNode | null = null;
  let counter = 0;

  const makeNode = (
    label: string,
    level: 0 | 1 | 2,
    detail?: TraceStep,
  ): TreeNode => ({
    id: `node-${counter++}`,
    label,
    level,
    detail,
    children: [],
  });

  for (const entry of trace) {
    switch (entry.step) {
      case "research": {
        if (!currentMain) {
          currentMain = makeNode("Main Agent", 0);
          roots.push(currentMain);
        }
        currentResearcher = makeNode("Researcher", 1, entry);
        currentMain.children.push(currentResearcher);
        break;
      }
      case "research_result": {
        // Merge into the current researcher's detail
        if (currentResearcher && currentResearcher.detail) {
          currentResearcher.detail = {
            ...currentResearcher.detail,
            findings_length: entry.findings_length,
            total_docs: entry.total_docs,
          };
        }
        break;
      }
      case "tool_result": {
        const toolName = entry.tool || "tool";
        const toolNode = makeNode(toolName, 2, entry);
        if (currentResearcher) {
          currentResearcher.children.push(toolNode);
        } else if (currentMain) {
          currentMain.children.push(toolNode);
        }
        break;
      }
      case "draft": {
        if (!currentMain) {
          currentMain = makeNode("Main Agent", 0);
          roots.push(currentMain);
        }
        const writerNode = makeNode("Writer", 1, entry);
        currentMain.children.push(writerNode);
        break;
      }
      case "draft_result": {
        // Merge into the last writer child's detail
        if (currentMain) {
          const lastChild = currentMain.children[currentMain.children.length - 1];
          if (lastChild && lastChild.label === "Writer" && lastChild.detail) {
            lastChild.detail = {
              ...lastChild.detail,
              draft_length: entry.draft_length,
            };
          }
        }
        break;
      }
      case "finalize": {
        if (!currentMain) {
          currentMain = makeNode("Main Agent", 0, entry);
          roots.push(currentMain);
        } else {
          if (!currentMain.detail) {
            currentMain.detail = entry;
          } else {
            currentMain.detail = {
              ...currentMain.detail,
              answer_length: entry.answer_length,
            };
          }
        }
        break;
      }
      case "quality_check": {
        const qcNode = makeNode("Quality Check", 0, entry);
        roots.push(qcNode);
        currentMain = null;
        currentResearcher = null;
        break;
      }
      default: {
        if (!currentMain) {
          currentMain = makeNode("Main Agent", 0);
          roots.push(currentMain);
        }
        const fallbackNode = makeNode(entry.step, 1, entry);
        currentMain.children.push(fallbackNode);
        break;
      }
    }
  }

  return roots;
}

// ---------------------------------------------------------------------------
// Depth-first traversal to find the last node in the tree.
// ---------------------------------------------------------------------------

function findLastNode(nodes: TreeNode[]): TreeNode | null {
  if (nodes.length === 0) return null;
  const last = nodes[nodes.length - 1];
  if (last.children.length > 0) {
    const lastChild = findLastNode(last.children);
    if (lastChild) return lastChild;
  }
  return last;
}

function findPathToNode(
  nodes: TreeNode[],
  target: TreeNode,
  path: TreeNode[] = [],
): TreeNode[] | null {
  for (const node of nodes) {
    const currentPath = [...path, node];
    if (node === target) return currentPath;
    if (node.children.length > 0) {
      const found = findPathToNode(node.children, target, currentPath);
      if (found) return found;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// TraceTreeNode — recursive rendering component
// ---------------------------------------------------------------------------

function TraceTreeNode({
  node,
  runningPath,
}: {
  node: TreeNode;
  runningPath: TreeNode[];
}) {
  const [userExpanded, setUserExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const onRunningPath = runningPath.includes(node);
  const isLast = runningPath.length > 0 && runningPath[runningPath.length - 1] === node;
  const isRunning = onRunningPath && isLast;
  const expanded = userExpanded || onRunningPath;

  const hasDetail = node.detail && Object.keys(node.detail).length > 1;
  const hasChildren = node.children.length > 0;
  const isExpandable = hasDetail || hasChildren;

  const copyStep = () => {
    navigator.clipboard.writeText(JSON.stringify(node.detail, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Level-specific styling
  const labelClass = (() => {
    if (node.level === 0) {
      return isRunning ? "gradient-working" : "text-text";
    }
    if (node.level === 1) {
      return isRunning ? "gradient-working-dark" : "text-muted";
    }
    return "text-muted";
  })();

  const indentClass =
    node.level === 0
      ? ""
      : node.level === 1
        ? "pl-6"
        : "pl-12";

  const prefix =
    node.level === 0
      ? null
      : node.level === 1
        ? "├── "
        : "│   ├── ";

  const hasSpinner = isRunning && node.level <= 1;

  return (
    <div>
      <div className={cn("border-b border-line")}>
        <button
          onClick={() => isExpandable && setUserExpanded(!userExpanded)}
          className={cn(
            "w-full flex items-center gap-2 px-4 py-3 text-left",
            !isExpandable && "cursor-default",
          )}
        >
          {prefix && (
            <span className="font-mono text-[11px] text-line leading-none select-none">
              {prefix}
            </span>
          )}

          {hasSpinner ? (
            <span className="inline-block w-3 h-3 border border-accent border-t-transparent rounded-full animate-spin flex-shrink-0" />
          ) : (
            <span className="font-mono text-[11px] leading-none text-success">✓</span>
          )}

          <span
            className={cn(
              "font-mono text-[11px] uppercase tracking-widest",
              labelClass,
            )}
          >
            {node.label}
          </span>

          <div className="flex-1" />

          {isExpandable && (
            <span className="font-mono text-[10px] text-muted">
              {expanded ? "[-]" : "[+]"}
            </span>
          )}
        </button>
      </div>

      {expanded && (
        <>
          {/* Children */}
          {hasChildren &&
            node.children.map((child) => (
              <TraceTreeNode
                key={child.id}
                node={child}
                runningPath={runningPath}
              />
            ))}

          {/* JSON detail */}
          {hasDetail && (
            <div className={cn("px-4 pb-3", indentClass)}>
              <div className="flex justify-start mb-2">
                <button
                  onClick={copyStep}
                  className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-muted hover:text-text transition"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" /> Copy
                    </>
                  )}
                </button>
              </div>
              <pre className="font-mono text-[11px] text-muted whitespace-pre-wrap overflow-x-auto">
                {JSON.stringify(node.detail, null, 2)}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TraceChain — top-level component
// ---------------------------------------------------------------------------

export default function TraceChain({ trace, live }: TraceChainProps) {
  const [copiedFull, setCopiedFull] = useState(false);

  if (!trace || trace.length === 0) return null;

  const tree = buildTree(trace);
  const lastNode = findLastNode(tree);
  const runningPath = live && lastNode ? findPathToNode(tree, lastNode) ?? [] : [];

  const copyFullTrace = () => {
    navigator.clipboard.writeText(JSON.stringify(trace, null, 2));
    setCopiedFull(true);
    setTimeout(() => setCopiedFull(false), 2000);
  };

  return (
    <div className="w-full max-w-full md:max-w-[680px] mb-5 border border-line">
      {tree.map((node) => (
        <TraceTreeNode
          key={node.id}
          node={node}
          runningPath={runningPath}
        />
      ))}
      <div className="flex justify-start px-4 py-3 border-t border-line">
        <button
          onClick={copyFullTrace}
          className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-muted hover:text-text transition"
        >
          {copiedFull ? (
            <>
              <Check className="w-3 h-3" /> Copied
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" /> Copy Full Trace
            </>
          )}
        </button>
      </div>
    </div>
  );
}