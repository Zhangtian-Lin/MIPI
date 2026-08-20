const queues = ["来源候选", "实体消歧", "字段冲突", "发布审核"];

export default function AdminHome() {
  return <main><header><strong>MIPI Admin</strong><span>V0 本地环境</span></header><section><p className="eyebrow">OPERATIONS</p><h1>审核工作台</h1><p>当前为工程骨架，尚未连接真实数据。</p><div className="grid">{queues.map((queue) => <article key={queue}><h2>{queue}</h2><strong>0</strong><p>暂无待处理记录</p></article>)}</div></section></main>;
}

