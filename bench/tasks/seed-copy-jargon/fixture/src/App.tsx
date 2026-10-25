import { PLANS, formatPrice } from "./plans";

const FEATURES = [
  {
    icon: "⚡",
    title: "Lightning-Fast, Always-On Global Checks",
    body: "In today's fast-paced digital landscape, every second counts. That's why Tidewatch leverages a cutting-edge, globally distributed network of 6 monitoring regions to check your websites and APIs every 30 seconds, around the clock, 24/7/365. It's not just monitoring — it's a whole new paradigm of proactive, always-on visibility that empowers you to stay one step ahead.",
    points: [
      "— Real-time insights at your fingertips",
      "— Global coverage that scales with your ambitions",
      "— Zero-config setup that just works",
    ],
  },
  {
    icon: "🔔",
    title: "Smart, Noise-Free Alerting That Actually Matters",
    body: "Say goodbye to alert fatigue and hello to peace of mind. Our intelligent, AI-ready alerting engine only notifies you after a failure is confirmed from 2 separate regions, so false alarms become a thing of the past. Seamlessly route alerts to email, SMS, Slack and PagerDuty, and unlock a truly frictionless incident response workflow that keeps your entire team aligned, informed and empowered.",
    points: [
      "— Confirmation from multiple regions before anyone gets paged",
      "— Omnichannel delivery to the tools you already love",
      "— Fewer interruptions, more innovation",
    ],
  },
  {
    icon: "📊",
    title: "Beautiful, On-Brand Public Status Pages",
    body: "Transparency is the new currency of trust. With Tidewatch, you can effortlessly spin up stunning, fully customizable public status pages on your own domain, so your customers always know what's going on. Leverage the power of proactive communication to transform downtime from a moment of frustration into an opportunity to delight, build loyalty and unlock lasting brand value.",
    points: [
      "— Your logo, your colors, your domain",
      "— Automatic updates straight from your monitors",
      "— Trust that turns users into raving fans",
    ],
  },
];

const STEPS = [
  {
    title: "Paste your URL 🔗",
    body: "Simply drop in the URL of any website or API endpoint you want to keep an eye on. There's absolutely no agent to install, no complex configuration to wrestle with and no learning curve to climb. It truly could not be easier.",
  },
  {
    title: "Pick your channels 📣",
    body: "Choose exactly how and where you'd like to be notified when something goes wrong, whether that's email, SMS, Slack, PagerDuty or any combination of the above. You're always in full control of your alerting experience.",
  },
  {
    title: "Relax and grow 🌱",
    body: "That's it, you're done! The whole process takes about 2 minutes from start to finish. Now you can sit back, relax and focus on what you do best, building amazing products, while Tidewatch seamlessly watches over everything for you.",
  },
];

const FAQ = [
  {
    q: "Is there a free trial available? 🤔",
    a: "Absolutely! We believe that the best way to experience the transformative power of Tidewatch is to try it for yourself. That's why every new account gets a full 14-day free trial of the Team plan, and you don't even need to enter a credit card to get started. No strings attached, no risk, no hassle whatsoever.",
  },
  {
    q: "Can I cancel my subscription at any time?",
    a: "Yes, of course! We're firm believers that you should stay because you love Tidewatch, not because you're locked in. You can cancel your subscription at any time, directly from your account settings, with just a couple of clicks. If you cancel in the middle of a billing period, we'll automatically refund the unused portion on a prorated basis.",
  },
  {
    q: "Where exactly is my data stored?",
    a: "Your data security and privacy are our absolute top priority. When you create your workspace, you get to choose whether your monitoring data lives in our EU region (Frankfurt) or our US region (Virginia), and it never leaves the region you pick. We've built our infrastructure from the ground up with a security-first mindset.",
  },
  {
    q: "Can I export my historical monitoring data?",
    a: "Definitely! We strongly believe that your data belongs to you, full stop. At any time, you can seamlessly export the complete check history for any of your monitors as a CSV file, so you can leverage it in your own tools, dashboards and reports however you see fit.",
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
          <p className="eyebrow">✨ Introducing the future of uptime ✨</p>
          <h1>Unlock Next-Level Reliability With AI-Ready Uptime Intelligence 🚀</h1>
          <p className="lede">
            Tidewatch is the next-generation, all-in-one observability platform that empowers
            modern, forward-thinking teams to seamlessly monitor their websites and APIs, leverage
            real-time insights and unlock world-class uptime at scale. Whether you're a scrappy
            startup or a global enterprise, we're here to help you elevate your reliability game,
            delight your customers and drive meaningful business outcomes, all from one beautifully
            intuitive, single pane of glass.
          </p>
          <div className="hero-actions">
            <a className="button primary" href="/signup">
              Unlock your free trial 🚀
            </a>
            <a className="button" href="#how-it-works">
              See the magic in action
            </a>
          </div>
          <p className="fineprint">
            Join thousands of happy teams who have already transformed the way they think about
            uptime. No credit card required, ever. 🙌
          </p>
        </section>

        <section id="features" className="features">
          <h2>Everything You Need to Supercharge Your Uptime Strategy</h2>
          <p className="section-lede">
            We've thoughtfully packed a robust, best-in-class suite of powerful features into one
            seamless, easy-to-use solution, so you can spend less time firefighting and more time
            doing the work that truly moves the needle for your business.
          </p>
          <div className="feature-grid">
            {FEATURES.map((f) => (
              <article key={f.title} className="feature">
                <span className="feature-icon" aria-hidden="true">
                  {f.icon}
                </span>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
                <div className="points">
                  {f.points.map((p) => (
                    <p key={p}>{p}</p>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section id="how-it-works" className="steps">
          <h2>Getting Started Is Easier Than Ever Before</h2>
          <p className="section-lede">
            We've completely reimagined the onboarding experience from the ground up to be as
            frictionless and delightful as humanly possible. Here's how you can go from zero to
            fully monitored in just three simple, easy steps.
          </p>
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
          <h2>Simple, Transparent Pricing That Scales With Your Success 💸</h2>
          <p className="section-lede">
            At Tidewatch, we believe that world-class reliability shouldn't break the bank. That's
            why we offer flexible, value-packed plans for teams of every shape and size. And when
            you choose yearly billing, you'll unlock 2 months completely free, every single year.
          </p>
          <div className="plan-grid">
            {PLANS.map((plan) => (
              <article key={plan.id} className={plan.highlighted ? "plan highlighted" : "plan"}>
                {plan.highlighted && <p className="badge">🔥 Most popular</p>}
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
          <h2>Frequently Asked Questions 💡</h2>
          <p className="section-lede">
            Got questions? We've got answers! Here are some of the most common questions we hear
            from our amazing community of customers. Can't find what you're looking for? Our
            world-class support team is always just a message away.
          </p>
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
          <h2>Ready to Unlock Your Reliability Superpowers? 🚀</h2>
          <p>
            Don't let downtime hold you back for one more day. Join the growing movement of teams
            who are leveraging Tidewatch to seamlessly deliver the always-on experiences their
            customers expect and deserve. Your journey to uptime excellence starts right here,
            right now.
          </p>
          <a className="button primary" href="/signup">
            Get started for free today 🙌
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
