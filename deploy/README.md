# Deploy do Wolfpack Control Plane (AMP)

Instalação e gestão do Wolfpack Control Plane (AMP, Agent Management Platform) em clusters Kubernetes usando Helm, espelhando fielmente a arquitetura definida em `docker/docker-compose.production.yml`.

O chart foi desenhado para ser autossuficiente e executado com um único comando, trazendo valores padrão funcionais para desenvolvimento e permitindo parametrização completa para homologação e produção diretamente na linha de comando, sem necessidade de scripts auxiliares.

## O que sobe (Topologia de Produção)

O chart em `chart/wolfpack-control-plane` provisiona todos os componentes da topologia de produção:

| Componente | Imagem de Produção | Função |
|---|---|---|
| Frontend | `wolfpackaiagents/wolfpack-amp-frontend:0.1.0` | Servidor Nginx que entrega a SPA (Single Page Application, aplicação de página única) e atua como proxy reverso roteando `/api/` para o backend |
| Backend API | `wolfpackaiagents/wolfpack-amp-backend:0.1.2` | Aplicação FastAPI (Application Programming Interface, interface de programação de aplicações) com migrações via Alembic, telemetria e governança |
| PostgreSQL | `postgres:16-alpine` | Banco de dados relacional transacional primário com volume persistente via PVC (Persistent Volume Claim, solicitação de volume de armazenamento persistente) |
| ClickHouse | `clickhouse/clickhouse-server:24.8` | Banco colunar analítico de alta performance para espelhamento e consulta de telemetria |
| Inngest PostgreSQL | `postgres:16-alpine` | Instância dedicada de PostgreSQL para armazenamento de estado do orquestrador de eventos Inngest |
| Inngest Server | `inngest/inngest:latest` | Motor de execução de rotinas duráveis, retentativas e disparos de agendamentos |
| Redis | `redis:7-alpine` | Armazenamento em memória para controle de concorrência e limites de requisição |
| MinIO | `minio/minio:latest` | Armazenamento de objetos compatível com S3 para retenção de artefatos e eventos |
| Qdrant | `qdrant/qdrant:latest` | Banco vetorial para indexação e recuperação semântica de conhecimento |
| Ingress | `networking.k8s.io/v1` | Ponto de entrada HTTP unificado com suporte a TLS (Transport Layer Security, protocolo de segurança da camada de transporte) |
| Prometheus | `prom/prometheus:v2.54.1` | Coleta de métricas e observabilidade da API e do Redis (opcional, desabilitado por padrão) |

## Instalação e Atualização

### 1. Instalação rápida com valores padrão

Executa todo o stack com os padrões embutidos em um único comando:

```bash
helm upgrade --install wolfpack-control-plane ./deploy/chart/wolfpack-control-plane \
  --namespace wolfpack \
  --create-namespace
```

Após subir, utilize o encaminhamento de porta para acessar a interface:

```bash
kubectl port-forward -n wolfpack svc/wolfpack-control-plane-frontend 8080:80
```

E acesse no navegador: `http://localhost:8080`.

### 2. Instalação completa de produção com parâmetros inline

Para publicar com domínio próprio, TLS ativo e segredos protegidos:

```bash
helm upgrade --install wolfpack-control-plane ./deploy/chart/wolfpack-control-plane \
  --namespace wolfpack \
  --create-namespace \
  --set ingress.host="amp.suaempresa.com" \
  --set ingress.tls=true \
  --set ingress.tlsSecretName="wildcard-tls" \
  --set configmapData.TELEMETRY_STORAGE_BACKEND="clickhouse" \
  --set-string secretData.ADMIN_API_KEY="sk-admin-chave-secreta-producao" \
  --set-string secretData.JWT_SECRET="segredo-jwt-producao-aleatorio-32bytes" \
  --set-string secretData.PROVIDER_SECRETS_MASTER_KEY="chave-fernet-master-32bytes-base64" \
  --set-string secretData.POSTGRES_PASSWORD="senha-forte-postgres-producao" \
  --set-string secretData.CLICKHOUSE_PASSWORD="senha-forte-clickhouse-producao" \
  --set-string secretData.MINIO_ROOT_PASSWORD="senha-forte-minio-producao" \
  --set-string secretData.INNGEST_SIGNING_KEY="inngest-signing-key-hex" \
  --set-string secretData.INNGEST_EVENT_KEY="inngest-event-key-hex"
```

### 3. Uso com serviços gerenciados de nuvem (RDS, ElastiCache, S3)

Caso sua infraestrutura já forneça bancos ou armazenamentos externos, basta desativar os pods internos correspondentes e informar as conexões:

```bash
helm upgrade --install wolfpack-control-plane ./deploy/chart/wolfpack-control-plane \
  --namespace wolfpack \
  --create-namespace \
  --set postgres.enabled=false \
  --set-string externalDatabase.url="postgresql+psycopg://usuario:senha@meu-rds-postgres:5432/wolfpack" \
  --set redis.enabled=false \
  --set-string externalRedis.url="redis://meu-elasticache:6379/0" \
  --set clickhouse.enabled=false \
  --set-string externalClickhouse.host="clickhouse.suaempresa.com" \
  --set-string secretData.CLICKHOUSE_PASSWORD="senha-clickhouse" \
  --set minio.enabled=false \
  --set-string externalMinio.endpoint="https://s3.amazonaws.com" \
  --set ingress.host="amp.suaempresa.com" \
  --set ingress.tls=true
```

## Parâmetros Configuráveis (`values.yaml`)

### Aplicação (Backend e Frontend)

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `backend.replicaCount` | Quantidade de réplicas da API | `1` |
| `backend.image.repository` | Repositório da imagem da API | `wolfpackaiagents/wolfpack-amp-backend` |
| `backend.image.tag` | Versão da imagem da API | `0.1.2` |
| `backend.autoscaling.enabled` | Habilita HPA (Horizontal Pod Autoscaler, escalador horizontal automático de pods) | `false` |
| `frontend.replicaCount` | Quantidade de réplicas do frontend | `1` |
| `frontend.image.repository` | Repositório da imagem do frontend | `wolfpackaiagents/wolfpack-amp-frontend` |
| `frontend.image.tag` | Versão da imagem do frontend | `0.1.0` |

### Ingress e Rede

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `ingress.enabled` | Cria o recurso de Ingress | `true` |
| `ingress.host` | Host DNS (Domain Name System, sistema de nomes de domínio) para acesso | `amp.local` |
| `ingress.className` | IngressClass do controlador (ex: `nginx`) | `""` |
| `ingress.tls` | Ativa terminação TLS no Ingress | `false` |
| `ingress.tlsSecretName` | Nome do secret TLS com o certificado | `wildcard-tls` |

### Serviços de Dados e Armazenamento

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `postgres.enabled` | Sobe pod PostgreSQL transacional interno | `true` |
| `postgres.persistence.size` | Tamanho do volume do PostgreSQL | `10Gi` |
| `clickhouse.enabled` | Sobe pod ClickHouse analítico interno | `true` |
| `clickhouse.persistence.size` | Tamanho do volume do ClickHouse | `20Gi` |
| `inngestPostgres.enabled` | Sobe PostgreSQL dedicado para o Inngest | `true` |
| `inngestPostgres.persistence.size` | Tamanho do volume do banco do Inngest | `5Gi` |
| `redis.enabled` | Sobe pod Redis interno | `true` |
| `redis.persistence.size` | Tamanho do volume do Redis | `2Gi` |
| `minio.enabled` | Sobe pod MinIO interno | `true` |
| `minio.persistence.size` | Tamanho do volume do MinIO | `10Gi` |
| `qdrant.enabled` | Sobe pod Qdrant interno | `true` |
| `qdrant.persistence.size` | Tamanho do volume do Qdrant | `10Gi` |
| `inngest.enabled` | Sobe servidor Inngest interno | `true` |

### Segredos (`secretData`)

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `secretData.ADMIN_API_KEY` | Chave de administração para criação de organizações e projetos | Chave de desenvolvimento |
| `secretData.JWT_SECRET` | Chave de assinatura dos tokens JWT (JSON Web Token, padrão de token de autenticação em formato JSON) | Chave de desenvolvimento |
| `secretData.PROVIDER_SECRETS_MASTER_KEY` | Chave mestra Fernet de 32 bytes para criptografia de credenciais de canais | Chave de desenvolvimento |
| `secretData.POSTGRES_PASSWORD` | Senha de acesso aos bancos PostgreSQL | Chave de desenvolvimento |
| `secretData.CLICKHOUSE_PASSWORD` | Senha de acesso ao ClickHouse | Chave de desenvolvimento |
| `secretData.MINIO_ROOT_PASSWORD` | Senha de administração do MinIO | Chave de desenvolvimento |

## Validação dos Manifestos

Antes de aplicar em um cluster, você pode validar o chart localmente:

```bash
# Validar sintaxe
helm lint deploy/chart/wolfpack-control-plane

# Renderizar manifestos localmente
helm template wolfpack-control-plane deploy/chart/wolfpack-control-plane
```
