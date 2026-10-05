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
  </div>;
}
