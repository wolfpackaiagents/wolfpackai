export default function AuthorPage() {
  return (
    <article className="max-w-3xl space-y-8">
      <header className="border-b border-gray-800 pb-8">
        <p className="text-xs font-semibold tracking-[.14em] text-amber-400">PROJECT AUTHOR</p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-white">Álvaro Brito</h1>
        <a
          href="https://www.linkedin.com/in/alvarogomes/"
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-flex text-sm font-medium text-amber-400 hover:text-amber-300"
        >
          Connect on LinkedIn
        </a>
      </header>

      <div className="space-y-5 text-lg leading-8 text-gray-300">
        <p>
          Backend and AI Engineer with 10+ years of experience architecting secure, scalable microservices and delivering modern LLM/RAG solutions. This engineer combines deep proficiency in Node.js, TypeScript, Python, Express, and PostgreSQL with infrastructure-grade execution on AWS, Docker, Terraform, and event-driven architectures.
        </p>
        <p>
          This developer builds observable AI workflows using LangChain and Langfuse, instrumenting LLM evaluations and operational metrics with Prometheus and Grafana to improve quality and reliability.
        </p>
        <p>
          This specialist focuses on turning complex workflows into production-ready platforms, automating CI/CD with Jenkins and other pipelines, orchestrating real-time systems, and supporting high-throughput data flows with FastAPI and Kafka. Overall, this engineer stands out by bridging mature backend engineering with measurable, production-grade generative AI delivery.
        </p>
      </div>
    </article>
  );
}
