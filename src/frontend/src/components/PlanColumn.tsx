/**
 * Right-hand column hosting the plan panel.
 *
 * This is the right-side sibling of ``Sidebar`` in the three-column
 * chat layout. It's a thin wrapper around ``PlanPanel`` that gives the
 * plan its own width-controlled column rather than living stacked
 * inside the sidebar.
 *
 * Width is controlled by ``App.tsx`` via the ``width`` prop (driven by
 * a ``Splitter`` between the chat area and this column).
 */

import PlanPanel from "./PlanPanel";
import type { Plan } from "../hooks/usePlan";
import type { AgentInfo } from "../hooks/useAgents";
import type { PipelineStage, ReviewState } from "../hooks/useWebSocket";

interface Props {
  width: number;
  plan: Plan;
  planMarkdown: string;
  reviewState: ReviewState;
  pipelineStage: PipelineStage | null;
  agents: AgentInfo[];
  onApprovePlan: () => void;
  onEditPlan: (markdown: string) => void;
  onPlanFeedback: (text: string) => void;
  onApproveAssignments: () => void;
  onEditAssignments: (markdown: string) => void;
  onAssignmentsFeedback: (text: string) => void;
  onCancelRun: () => void;
}

export default function PlanColumn({
  width,
  plan,
  planMarkdown,
  reviewState,
  pipelineStage,
  agents,
  onApprovePlan,
  onEditPlan,
  onPlanFeedback,
  onApproveAssignments,
  onEditAssignments,
  onAssignmentsFeedback,
  onCancelRun,
}: Props) {
  return (
    <aside
      className="plan-column"
      style={{ width: `${width}px`, minWidth: `${width}px` }}
      aria-label="Plan"
    >
      <PlanPanel
        plan={plan}
        markdown={planMarkdown}
        reviewState={reviewState}
        pipelineStage={pipelineStage}
        agents={agents}
        onApprovePlan={onApprovePlan}
        onEditPlan={onEditPlan}
        onPlanFeedback={onPlanFeedback}
        onApproveAssignments={onApproveAssignments}
        onEditAssignments={onEditAssignments}
        onAssignmentsFeedback={onAssignmentsFeedback}
        onCancelRun={onCancelRun}
      />
    </aside>
  );
}
