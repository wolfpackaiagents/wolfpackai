import * as fs from "node:fs";
import * as path from "node:path";
import { fal } from "@fal-ai/client";

const FAL_KEY = process.env.FAL_KEY;
if (!FAL_KEY) {
  console.error("FAL_KEY environment variable is required");
  process.exit(1);
}

fal.config({
  credentials: FAL_KEY,
});

const prompts = [
  {
    name: "agent-loop",
    prompt:
      "Professional software architecture diagram showing Wolfpack AI Agent loop with model, tools, memory, guardrails, observer - clean minimal design, dark background, tech blueprint style, 4k quality",
    description: "Agent Loop Architecture",
  },
  {
    name: "team-delegation",
    prompt:
      "System architecture diagram of Wolfpack AI Team delegation with leader model delegating to specialist agents, clean modern design, dark background, data flow arrows",
    description: "Team Delegation Architecture",
  },
  {
    name: "amp-control-plane",
    prompt:
      "Wolfpack Agent Management Platform (AMP) control plane architecture showing Mesh, Chat, Channels, Schedules, clean minimal diagram, dark background",
    description: "AMP Control Plane",
  },
  {
    name: "observer-data-flow",
    prompt:
      "Data flow diagram of Wolfpack Observer sending telemetry to AMP ingestion pipeline, clean modern design, dark background, showing traces and metrics pipeline",
    description: "Observer Data Flow",
  },
  {
    name: "chat-architecture",
    prompt:
      "Chat architecture showing frontend, AMP gateway, and external agent runtime with chat_endpoint, clean technical diagram, dark background",
    description: "Chat Architecture",
  },
  {
    name: "framework-overview",
    prompt:
      "Wolfpack framework overview showing all components: Agent, Tools, Team, Memory, Knowledge, Guardrails, Workflow, clean comprehensive architecture diagram, dark background",
    description: "Framework Overview",
  },
];

async function generateDiagram(prompt: string): Promise<Buffer> {
  const result = await fal.subscribe("fal-ai/nano-banana-pro", {
    input: { prompt, image_size: "landscape_16_9" },
    logs: true,
    onQueueUpdate(update: any) {
      if (update.status === "IN_PROGRESS") {
        const logs = update.logs?.map((l: any) => l.message).filter(Boolean).join(", ");
        console.log(`  Queue: ${logs || "processing..."}`);
      }
    },
  });

  const resultData = result as any;
  const imageUrl = resultData.images?.[0]?.url || resultData.data?.images?.[0]?.url || resultData.image?.url;
  if (!imageUrl) {
    throw new Error("No image URL in response: " + JSON.stringify(result));
  }

  const response = await fetch(imageUrl);
  if (!response.ok) {
    throw new Error(`Failed to download image: ${response.status}`);
  }

  const buffer = Buffer.from(await response.arrayBuffer());
  return buffer;
}

async function main() {
  const outputDir = path.resolve(process.cwd(), "public", "diagrams");
  fs.mkdirSync(outputDir, { recursive: true });

  console.log(`Generating ${prompts.length} diagrams with fal.ai nano-banana-pro...\n`);

  for (const item of prompts) {
    console.log(`[${item.name}] ${item.description}`);
    try {
      const buffer = await generateDiagram(item.prompt);
      const filePath = path.join(outputDir, `${item.name}.png`);
      fs.writeFileSync(filePath, buffer);
      console.log(`  OK Saved to ${filePath} (${(buffer.length / 1024).toFixed(1)} KB)\n`);
    } catch (err) {
      console.error(`  FAILED: ${err instanceof Error ? err.message : err}\n`);
    }
  }

  console.log("Done!");
}

main().catch(console.error);