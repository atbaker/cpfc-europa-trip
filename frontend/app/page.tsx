import { PlannerForm } from "../components/planner-form";

export default function Home() {
  return <div className="home-page">
    <div className="home">
      <section className="intro">
        <p className="eyebrow">EUROPEAN AWAY DAYS · 2026 / 27</p>
        <h1>Follow Palace.<br /><em>Make a trip of it.</em></h1>
        <p className="lead">Choose an away match and a UK starting city. We’ll help you compare the journey and find a place to stay.</p>
        <p className="intro-note">A practical trip plan with real prices where available. You book directly with travel providers.</p>
      </section>
      <PlannerForm />
    </div>
    <section className="example-plan" aria-labelledby="example-title">
      <div className="section-heading"><div><p className="eyebrow">WHAT YOUR PLAN COULD LOOK LIKE</p><h2 id="example-title">A trip at a glance</h2></div><span className="tag">Illustrative example</span></div>
      <div className="example-route"><div><small>Journey</small><strong>London → Lyon</strong></div><div><small>Return flight</small><strong>£268</strong></div><div><small>Stay with indicated tax</small><strong>£63</strong></div><div><small>Prices found so far</small><strong>£331</strong></div></div>
      <p className="fine">These prices were found on 2 October 2026 and are only an example. A new plan searches again. Baggage, local transfers and match tickets may add to the cost.</p>
    </section>
  </div>;
}
