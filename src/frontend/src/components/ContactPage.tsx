/**
 * Contact page — single-column. Project link and the people behind the
 * work. Quiet aesthetic; this is where someone goes when they want a
 * human, not an issue tracker.
 */

export default function ContactPage() {
  return (
    <article className="doc-page">
      <header className="doc-header">
        <p className="doc-eyebrow">CONTACT</p>
        <h1 className="doc-title">Get in touch</h1>
        <p className="doc-lede">
          Questions, bug reports, feature requests, and collaboration
          enquiries are all welcome.
        </p>
      </header>

      <section className="doc-section">
        <h2>Project home</h2>
        <p>
          The canonical source lives on GitHub. File issues there,
          send pull requests there, and watch the repository to be
          notified about new releases.
        </p>
        <p className="doc-actions">
          <a
            className="doc-link-btn"
            href="https://github.com/ma-compbio/TissueAgent"
            target="_blank"
            rel="noreferrer noopener"
          >
            github.com/ma-compbio/TissueAgent
          </a>
        </p>
      </section>

      <section className="doc-section">
        <h2>Contact information</h2>
        <p>
          For research collaborations, security disclosures, and
          anything that doesn&apos;t fit a public issue tracker, reach
          out to one of us directly.
        </p>
        <ul className="doc-people-list">
          <li>
            <span className="doc-person-name">Wenduo Cheng</span>
            <a
              className="doc-person-email"
              href="mailto:wenduoc@andrew.cmu.edu"
            >
              wenduoc@andrew.cmu.edu
            </a>
          </li>
          <li>
            <span className="doc-person-name">Dustin Miao</span>
            <a
              className="doc-person-email"
              href="mailto:dustinmi@andrew.cmu.edu"
            >
              dustinmi@andrew.cmu.edu
            </a>
          </li>
          <li>
            <span className="doc-person-name">
              <a
                className="doc-person-link"
                href="https://www.cs.cmu.edu/~jianma/"
                target="_blank"
                rel="noreferrer noopener"
              >
                Jian Ma
                <span aria-hidden="true"> ↗</span>
              </a>
            </span>
            <a
              className="doc-person-email"
              href="mailto:jianma@cs.cmu.edu"
            >
              jianma@cs.cmu.edu
            </a>
          </li>
        </ul>
      </section>
    </article>
  );
}
