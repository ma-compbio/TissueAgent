/**
 * Tutorial page — single-column editorial layout that reads like a
 * lab notebook's table of contents and chapter listing.
 *
 * Design vocabulary borrowed from the rest of the app:
 *   - Tabular mono numeric indices (01, 02, ...) as the structural
 *     anchor, matching the pipeline-stepper and plan-step layouts.
 *   - Display font (Bricolage Grotesque) for titles, body sans for
 *     prose, mono (Geist Mono) for indices, agent IDs, and paths.
 *   - One accent color (instrument-cyan) used sparingly to mark
 *     active state and clickable anchors.
 */

import { useEffect, useState } from "react";

const FIG_SRC = "/tissueagent_overall_design.png";
const FIG_ALT =
  "TissueAgent overall design: (a) Concept — user provides text, dataset, PDF, or image; TissueAgent dispatches a query to internal and external expert agents and produces task outputs like cell type annotation, deconvolution, figure reproduction, differential gene expression, cell-cell communication, and hypothesis generation. (b) Workflow — Planner retrieves and adapts a plan, Recruiter forms a research team, Manager executes plan steps, Evaluator decides whether to replan or output, Reporter writes the summary and notebook. (c) Plan-updating routine — each step records Step, Reason, Expected Artifacts, Assigned Agent, Assignment Rationale, Execution Result, and Execution Artifacts contributed by the Planner, Recruiter, Manager, and Evaluator.";

interface Chapter {
  id: string;
  title: string;
}

const CHAPTERS: Chapter[] = [
  { id: "overview", title: "Overview" },
  { id: "modes", title: "Autopilot vs. Copilot" },
  { id: "first-run", title: "Your first run" },
  { id: "plan", title: "The evolving plan" },
  { id: "files", title: "Files and sessions" },
  { id: "exports", title: "Exports" },
];

const pad = (n: number) => String(n).padStart(2, "0");

export default function TutorialPage() {
  const [lightboxOpen, setLightboxOpen] = useState(false);

  // ESC closes the lightbox; lock body scroll while it's open.
  useEffect(() => {
    if (!lightboxOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [lightboxOpen]);

  return (
    <div className="doc-layout">
      {/* Left sidebar — table of contents (sticky) ------------------- */}
      <aside className="doc-contents-aside" aria-label="Table of contents">
        <p className="doc-contents-label">Contents</p>
        <ol className="doc-contents-list">
          {CHAPTERS.map((ch, i) => (
            <li key={ch.id}>
              <a href={`#${ch.id}`}>
                <span className="doc-contents-num">{pad(i + 1)}</span>
                <span className="doc-contents-title">{ch.title}</span>
              </a>
            </li>
          ))}
        </ol>
      </aside>

      {/* Right column — the actual content --------------------------- */}
      <article className="doc-page">
        {/* Hero -------------------------------------------------------- */}
        <header className="doc-header">
          <p className="doc-eyebrow">Getting started</p>
          <h1 className="doc-title">TissueAgent Tutorial</h1>
        </header>

        {/* §01 Overview ----------------------------------------------- */}
      <Section id="overview" index={1} title="Overview">
        {/* Method figure — floats right so the body text wraps around it.
            Clickable thumbnail; lightbox opens at full size. */}
        <figure className="doc-figure doc-figure-float">
          <button
            type="button"
            className="doc-figure-thumb"
            onClick={() => setLightboxOpen(true)}
            aria-label="Open the TissueAgent overview figure at full size"
          >
            <img src={FIG_SRC} alt={FIG_ALT} loading="lazy" />
            <span className="doc-figure-zoom" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.4" />
                <line x1="9.5" y1="9.5" x2="13" y2="13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                <line x1="6" y1="3.6" x2="6" y2="8.4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="3.6" y1="6" x2="8.4" y2="6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              <span>Click to enlarge</span>
            </span>
          </button>
          <figcaption>
            Overview of TissueAgent.{" "}
            <strong>a · Concept.</strong> A user submits a text query
            and heterogeneous inputs (dataset files, PDFs, images).
            TissueAgent routes the request to a pool of expert agents
            to address a variety of spatial transcriptomics tasks.{" "}
            <strong>b · Workflow.</strong> The core framework
            comprises a Planner, Recruiter, Manager, Evaluator, and
            Reporter.{" "}
            <strong>c · Plan-updating routine.</strong> A single
            evolving plan serves as shared memory and a coordination
            protocol.
          </figcaption>
        </figure>

        <p>
          TissueAgent is a role-based multi-agent framework for spatial
          transcriptomics. Five main agents coordinate the work, each
          with a narrow role and a clear hand-off.
        </p>

        <ol className="doc-pipeline">
          <li>
            <span className="doc-pipeline-name">Planner</span>
            <span className="doc-pipeline-desc">
              Reads your request and drafts a plan. Either adapts a
              template from the plan registry or writes one from
              scratch.
            </span>
          </li>
          <li>
            <span className="doc-pipeline-name">Recruiter</span>
            <span className="doc-pipeline-desc">
              Assigns an expert agent to each step of the plan.
            </span>
          </li>
          <li>
            <span className="doc-pipeline-name">Manager</span>
            <span className="doc-pipeline-desc">
              Executes the plan in order. Hands each step off to its
              assigned expert and collects the output.
            </span>
          </li>
          <li>
            <span className="doc-pipeline-name">Evaluator</span>
            <span className="doc-pipeline-desc">
              Checks the produced artifacts against the plan&apos;s
              expectations. May trigger a replan if the results
              don&apos;t hold up.
            </span>
          </li>
          <li>
            <span className="doc-pipeline-name">Reporter</span>
            <span className="doc-pipeline-desc">
              Summarizes what happened and surfaces the final
              artifacts.
            </span>
          </li>
        </ol>

        <h3 className="doc-subhead">Expert agents</h3>
        <p>
          Each plan step is handed off to one expert agent from the
          registry. When no expert fits, the recruiter falls back to{" "}
          <code>coding_agent</code> and explains the choice in the
          assignment rationale.
        </p>
        <dl className="doc-agents">
          <dt><code>coding_agent</code></dt>
          <dd>General-purpose Python execution</dd>
          <dt><code>cell_annotator_agent</code></dt>
          <dd>Harmony-based label transfer</dd>
          <dt><code>spot_agent</code></dt>
          <dd>cell2location for Visium deconvolution</dd>
          <dt><code>single_cell_agent</code></dt>
          <dd>scRNA-seq processing</dd>
          <dt><code>gene_agent</code></dt>
          <dd>Biological reasoning about gene lists</dd>
          <dt><code>hypothesis_agent</code></dt>
          <dd>Hypothesis generation and testing</dd>
          <dt><code>pdf_reader_agent</code></dt>
          <dd>Reads attached PDFs</dd>
          <dt><code>searcher_agent</code></dt>
          <dd>Web and literature search</dd>
          <dt><code>critic_agent</code></dt>
          <dd>Falsification and confound review</dd>
        </dl>
      </Section>

      {/* §02 Autopilot vs. Copilot ----------------------------------- */}
      <Section id="modes" index={2} title="Autopilot vs. Copilot">
        <p>
          TissueAgent supports two execution modes, switchable via the
          toggle at the top of the sidebar. The choice controls how
          much the agent asks before acting — pick the one that fits
          how much you want to supervise the run.
        </p>

        <table className="doc-compare">
          <colgroup>
            <col className="doc-compare-col-label" />
            <col />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th scope="col" aria-hidden="true" />
              <th scope="col">Autopilot</th>
              <th scope="col">Copilot</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">How it runs</th>
              <td>
                Planner → Recruiter → Manager → Evaluator → Reporter
                with no pauses.
              </td>
              <td>
                Pauses twice for your review: after the plan is
                drafted, and after agent assignments.
              </td>
            </tr>
            <tr>
              <th scope="row">Your role</th>
              <td>Read the result when it&apos;s done.</td>
              <td>
                Approve, edit, send feedback, or cancel at each gate.
              </td>
            </tr>
            <tr>
              <th scope="row">Best for</th>
              <td>
                Routine analyses where you don&apos;t need much
                background context to interpret what the agent will
                do.
              </td>
              <td>
                Ambiguous requests, or any analysis where you want
                control over each step.
              </td>
            </tr>
          </tbody>
        </table>
      </Section>

      {/* §03 Your first run ----------------------------------------- */}
      <Section id="first-run" index={3} title="Your first run">
        <ol className="doc-steps">
          <li>
            <div className="doc-step-body">
              <h3>Upload data</h3>
              <p>
                Drag an <code>.h5ad</code> file into the upload area
                in the sidebar, or click to browse. PDFs are accepted
                too — useful when you want the agent to read a paper
                alongside its companion dataset. Images (e.g. figure
                panels you want the agent to reason about) work as
                well.
              </p>
            </div>
          </li>
          <li>
            <div className="doc-step-body">
              <h3>Type a request</h3>
              <p>
                Plain English. The agent does the translation to
                code, libraries, and parameters.
              </p>
              <ul className="doc-examples">
                <li>
                  &ldquo;Annotate cell types in the uploaded spatial
                  dataset using a Harmony reference.&rdquo;
                </li>
                <li>
                  &ldquo;Run GO enrichment on the top 100
                  differentially expressed genes.&rdquo;
                </li>
                <li>&ldquo;Draw a UMAP colored by cluster.&rdquo;</li>
              </ul>
            </div>
          </li>
          <li>
            <div className="doc-step-body">
              <h3>Watch the plan emerge</h3>
              <p>
                The planner populates the plan panel on the right
                side of the sidebar with numbered steps, descriptions,
                and expected artifacts.
              </p>
            </div>
          </li>
          <li>
            <div className="doc-step-body">
              <h3>Review the result</h3>
              <p>
                Final outputs appear in the chat as the reporter
                agent summarizes them. Artifact paths are listed per
                step in the plan panel.
              </p>
            </div>
          </li>
        </ol>
      </Section>

      {/* §04 The evolving plan -------------------------------------- */}
      <Section id="plan" index={4} title="The evolving plan">
        <p>
          The plan panel on the right side of the sidebar is the
          single source of truth for what the agent intends to do, is
          doing, and has done. It updates live as the run progresses.
        </p>
        <dl className="doc-fields">
          <dt>Pipeline stepper</dt>
          <dd>
            Five stages across the top. Active stage breathes; done
            stages turn solid; the connector line fills in left to
            right.
          </dd>
          <dt>Status</dt>
          <dd>
            <code>draft</code> → <code>recruited</code> →{" "}
            <code>running</code> → <code>done</code>. In copilot mode,{" "}
            <code>awaiting_plan_review</code> and{" "}
            <code>awaiting_assignment_review</code> appear at the two
            gates.
          </dd>
          <dt>Provenance</dt>
          <dd>
            A small caption beneath the status: either{" "}
            <em>From template: <code>NAME</code></em> with the
            registry template id and decision score, or{" "}
            <em>De novo plan</em> when the planner wrote it from
            scratch.
          </dd>
          <dt>Steps</dt>
          <dd>
            Each step is numbered, titled, and carries a description,
            reasoning, expected artifacts, assigned agent, and (after
            execution) the actual outputs and parameters the agent
            used.
          </dd>
        </dl>
      </Section>

      {/* §05 Files and sessions ------------------------------------- */}
      <Section id="files" index={5} title="Files and sessions">
        <p>
          Uploaded files go to the <code>data/</code> directory and
          are visible to every agent. The file browser button in the
          sidebar opens the directory tree.
        </p>
        <p>
          <strong>Save session</strong> writes the full conversation,
          plan, prompts snapshot, and mode to a timestamped JSON file.{" "}
          <strong>Load</strong> restores it in place — no page
          reload. <strong>Delete</strong> removes the saved file.
        </p>
      </Section>

      {/* §06 Exports ------------------------------------------------ */}
      <Section id="exports" index={6} title="Exports">
        <dl className="doc-fields">
          <dt>HTML</dt>
          <dd>
            Styled, self-contained document with plan, conversation,
            and a collapsible prompts snapshot. Best for sharing with
            someone who won&apos;t open it in Markdown.
          </dd>
          <dt>Markdown</dt>
          <dd>
            Plain prose for pasting into a notebook, paper draft, or
            issue tracker. Plan first, then run parameters, then
            conversation, then prompts.
          </dd>
        </dl>
        <p>
          Both exports include provenance and per-step parameters so
          a colleague can audit what was actually done.
        </p>
      </Section>
      </article>

      {lightboxOpen && (
        <div
          className="doc-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="TissueAgent overview figure, enlarged"
          onClick={() => setLightboxOpen(false)}
        >
          <button
            type="button"
            className="doc-lightbox-close"
            onClick={(e) => {
              e.stopPropagation();
              setLightboxOpen(false);
            }}
            aria-label="Close enlarged figure"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <line x1="3" y1="3" x2="13" y2="13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="13" y1="3" x2="3" y2="13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          <img
            className="doc-lightbox-img"
            src={FIG_SRC}
            alt={FIG_ALT}
            onClick={(e) => e.stopPropagation()}
          />
          <p className="doc-lightbox-hint">Press ESC or click outside to close</p>
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------
// Section header with a §-prefixed copyable anchor link.
// ----------------------------------------------------------------------

interface SectionProps {
  id: string;
  index: number;
  title: string;
  children: React.ReactNode;
}

function Section({ id, index, title, children }: SectionProps) {
  return (
    <section id={id} className="doc-section">
      <h2 className="doc-section-head">
        <a
          href={`#${id}`}
          className="doc-section-anchor"
          aria-label={`Section ${pad(index)}, ${title}. Copy link by clicking.`}
        >
          <span className="doc-section-num">§{pad(index)}</span>
          <span className="doc-section-title">{title}</span>
        </a>
      </h2>
      {children}
    </section>
  );
}
