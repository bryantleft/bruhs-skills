import { PLANS, formatPrice } from "./plans";

const FEATURES = [
  {
    title: "Checks every 30 seconds",
    body: "Tidewatch checks your websites and APIs every 30 seconds from 6 regions, day and night.",
  },
  {
    title: "Alerts you can trust",
    body: "We only alert you once 2 regions confirm a failure, so a blip in one place won't wake anyone up. Alerts go to email, SMS, Slack or PagerDuty.",
  },
  {
    title: "Public status pages",
    body: "Give customers a status page on your own domain, with your logo and colors. It updates itself from your monitors.",
  },
];

const STEPS = [
  {
    title: "Paste a URL",
    body: "Any website or API endpoint. There's no agent to install.",
  },
  {
    title: "Pick where alerts go",
    body: "Email, SMS, Slack, PagerDuty, or any mix.",
  },
  {
    title: "That's it",
    body: "Setup takes about 2 minutes.",
  },
];

const FAQ = [
  {
    q: "Is there a free trial?",
    a: "Yes. New accounts get 14 days of the Team plan for free, no credit card needed.",
  },
  {
    q: "Can I cancel at any time?",
    a: "Yes, from your account settings. If you cancel partway through a billing period, we refund the unused part.",
  },
  {
    q: "Where is my data stored?",
    a: "In the EU (Frankfurt) or the US (Virginia). You pick when you create your workspace, and your data never leaves that region.",
  },
  {
    q: "Can I export my data?",
    a: "Yes. You can export any monitor's check history as a CSV file.",
  },
];

export function App() {
  return (
    <div className="site">
      <header className="nav">
        <a className="brand" href="/">
          Tidewatch
        </a>
        <nav>
          <a href="#features">Features</a>
          <a href="#pricing">Pricing</a>
          <a href="#faq">FAQ</a>
          <a className="nav-cta" href="/signup">
            Sign up
          </a>
        </nav>
      </header>

      <main>
        <section id="hero" className="hero">
          <p className="eyebrow">Uptime monitoring</p>
          <h1>Know when your site goes down, before your customers do</h1>
          <p className="lede">
            Tidewatch checks your websites and APIs around the clock and alerts you the moment
            one stops responding.
          </p>
          <div className="hero-actions">
            <a className="button primary" href="/signup">
              Start a free trial
            </a>
            <a className="button" href="#how-it-works">
              How it works
            </a>
          </div>
          <p className="fineprint">No credit card needed.</p>
        </section>

        <section id="features" className="features">
          <h2>What you get</h2>
          <div className="feature-grid">
            {FEATURES.map((f) => (
              <article key={f.title} className="feature">
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="how-it-works" className="steps">
          <h2>How it works</h2>
          <ol className="step-list">
            {STEPS.map((s) => (
              <li key={s.title}>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="pricing" className="pricing">
          <h2>Pricing</h2>
          <p className="section-lede">Pay yearly and get 2 months free.</p>
          <div className="plan-grid">
            {PLANS.map((plan) => (
              <article key={plan.id} className={plan.highlighted ? "plan highlighted" : "plan"}>
                {plan.highlighted && <p className="badge">Most popular</p>}
                <h3>{plan.name}</h3>
                <p className="price">
                  {formatPrice(plan.monthlyCents)}
                  {plan.monthlyCents > 0 && <span className="per">/month</span>}
                </p>
                <p className="tagline">{plan.tagline}</p>
                <ul>
                  {plan.features.map((feature) => (
                    <li key={feature}>{feature}</li>
                  ))}
                </ul>
                <a className="button primary" href={`/signup?plan=${plan.id}`}>
                  {plan.cta}
                </a>
              </article>
            ))}
          </div>
        </section>

        <section id="faq" className="faq">
          <h2>Questions</h2>
          <dl>
            {FAQ.map((item) => (
              <div key={item.q} className="faq-item">
                <dt>{item.q}</dt>
                <dd>{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section id="get-started" className="closing">
          <h2>Start monitoring in 2 minutes</h2>
          <p>Try the Team plan free for 14 days.</p>
          <a className="button primary" href="/signup">
            Start a free trial
          </a>
        </section>
      </main>

      <footer className="footer">
        <p>© 2026 Tidewatch Labs, Inc.</p>
        <nav>
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
          <a href="mailto:hello@tidewatch.dev">hello@tidewatch.dev</a>
        </nav>
      </footer>
    </div>
  );
}
