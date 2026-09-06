import { Link } from "react-router-dom";
import { useI18n } from "../i18n/context";

export default function AuthorPage() {
  const { lang, t } = useI18n();
  return (
    <article className="max-w-3xl space-y-8">
      <header className="border-b border-gray-800 pb-8">
        <p className="text-xs font-semibold tracking-[.14em] text-amber-400">{t.author.projectAuthor}</p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-white">Álvaro Brito</h1>
        <a
          href="https://www.linkedin.com/in/alvarogomes/"
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-flex text-sm font-medium text-amber-400 hover:text-amber-300"
        >
          {t.author.connectLinkedin}
        </a>
      </header>

      <div className="space-y-5 text-lg leading-8 text-gray-300">
        <p>
          {lang === "pt-BR" ? "Engenheiro de backend e IA com mais de dez anos de experiencia em arquitetura de microsservicos seguros e escalaveis e em solucoes modernas de LLM e RAG. Combina Node.js, TypeScript, Python, Express e PostgreSQL com execucao de infraestrutura em AWS, Docker, Terraform e arquiteturas orientadas a eventos." : "Backend and AI Engineer with 10+ years of experience architecting secure, scalable microservices and delivering modern LLM/RAG solutions. This engineer combines deep proficiency in Node.js, TypeScript, Python, Express, and PostgreSQL with infrastructure-grade execution on AWS, Docker, Terraform, and event-driven architectures."}
        </p>
        <p>
          {lang === "pt-BR" ? "Desenvolve workflows de IA observaveis com LangChain e Langfuse, instrumentando avaliacoes de LLM e metricas operacionais com Prometheus e Grafana para aumentar a qualidade e a confiabilidade." : "This developer builds observable AI workflows using LangChain and Langfuse, instrumenting LLM evaluations and operational metrics with Prometheus and Grafana to improve quality and reliability."}
        </p>
        <p>
          {lang === "pt-BR" ? "Seu foco e transformar workflows complexos em plataformas prontas para producao, automatizar CI/CD com Jenkins e outros pipelines, orquestrar sistemas em tempo real e suportar fluxos de dados de alto volume com FastAPI e Kafka." : "This specialist focuses on turning complex workflows into production-ready platforms, automating CI/CD with Jenkins and other pipelines, orchestrating real-time systems, and supporting high-throughput data flows with FastAPI and Kafka. Overall, this engineer stands out by bridging mature backend engineering with measurable, production-grade generative AI delivery."}
        </p>
      </div>
    </article>
  );
}
