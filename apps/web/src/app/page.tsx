import { StatusBadge } from "@mipi/ui-web";

const industries = ["数据中心与 AI 基础设施", "半导体", "先进制造与新能源"];

export default function HomePage() {
  return (
    <main>
      <header className="site-header">
        <a className="brand" href="/">MIPI</a>
        <nav aria-label="主导航">
          <a href="#changes">重要变化</a>
          <a href="#industries">产业</a>
          <a href="#states">州属</a>
          <a href="#methodology">方法论</a>
        </nav>
      </header>

      <section className="hero">
        <StatusBadge level="F0">工程初始化</StatusBadge>
        <h1>马来西亚产业与政策情报</h1>
        <p>把分散的政策、投资、项目与企业信息，整理成可查询、可追踪、可验证的结构化知识。</p>
        <label className="search-shell">
          <span className="sr-only">搜索</span>
          <input disabled placeholder="搜索企业、项目、政策或提问……" />
          <button disabled>搜索</button>
        </label>
        <p className="notice">当前为 V0 工程骨架，不包含真实情报数据。</p>
      </section>

      <section id="changes" className="section">
        <div className="section-heading">
          <div><span className="eyebrow">TODAY</span><h2>今日重要变化</h2></div>
          <span className="muted">等待接入已审核数据</span>
        </div>
        <div className="empty-state">尚未收录可公开事件。真实数据必须经过来源、证据和验证流程。</div>
      </section>

      <section id="industries" className="section">
        <div className="section-heading"><div><span className="eyebrow">SECTORS</span><h2>重点产业</h2></div></div>
        <div className="card-grid">
          {industries.map((industry) => <article className="card" key={industry}><h3>{industry}</h3><p>产业页面模块已预留，等待 View Model 和 API。</p></article>)}
        </div>
      </section>

      <section id="states" className="section split">
        <article><span className="eyebrow">STATES</span><h2>重点州属</h2><p>Johor · Penang · Selangor · Kuala Lumpur</p></article>
        <article id="methodology"><span className="eyebrow">TRUST</span><h2>证据优先</h2><p>S1–S6 描述来源，F0–F4 描述事实验证。关键字段必须能回到原文证据。</p></article>
      </section>
    </main>
  );
}

