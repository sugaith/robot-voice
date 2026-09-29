/**
 * robot-voice for pi: speaks each finished reply, and adds /robot.
 *
 * Pi runs this inside its own process, so nothing here waits on audio: the
 * reply goes to a detached `python3 -m robot_voice _job`, the same core the
 * Claude Code and Hermes adapters use, and /robot:<command> runs the CLI and
 * shows its output as a notification, without a model turn.
 */
import { execFile, spawn } from "node:child_process";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const ROOT = path.resolve(__dirname, "..");
const PYTHON = process.env.ROBOT_VOICE_HOOK_PYTHON || "python3";

const COMMANDS: Record<string, string> = {
	use: "Robot voice: switch engine or voice -- <engine> [voice], a voice, or plain words",
	voice: "Robot voice: show the current voices, or set one",
	all: "Robot voice: say the last reply again, all of it",
	tldr: "Robot voice: a short summary of the last reply (3-5 sentences)",
	brief: "Robot voice: the last reply's first sentence again",
	vol: "Robot voice: how loud, 0 to 10 (5 is normal, 10 twice as loud)",
	help: "Robot voice: the commands",
};

function env(): NodeJS.ProcessEnv {
	const prior = process.env.PYTHONPATH;
	return { ...process.env, PYTHONPATH: prior ? `${ROOT}${path.delimiter}${prior}` : ROOT };
}

/** "pi:<id>". Also exported to the environment, so robot-voice commands the
 * agent runs from its bash tool act on this session too. */
function session(ctx: any): string {
	const sid = `pi:${ctx.sessionManager.getSessionId()}`;
	process.env.ROBOT_VOICE_SESSION = sid;
	return sid;
}

function replyText(messages: any[]): string {
	for (let i = messages.length - 1; i >= 0; i--) {
		const m = messages[i];
		if (m?.role !== "assistant") continue;
		if (typeof m.content === "string") return m.content;
		if (Array.isArray(m.content)) {
			return m.content
				.filter((b: any) => b?.type === "text" && typeof b.text === "string")
				.map((b: any) => b.text)
				.join("\n");
		}
		return "";
	}
	return "";
}

function speak(text: string, session: string): void {
	try {
		const child = spawn(PYTHON, ["-m", "robot_voice", "_job"], {
			cwd: ROOT,
			env: env(),
			detached: true,
			stdio: ["pipe", "ignore", "ignore"],
		});
		child.on("error", () => {}); // no python3: stay silent, never break the session
		child.stdin?.end(JSON.stringify({ op: "reply", text, session }));
		child.unref();
	} catch {
		// a broken speaker must never break a turn
	}
}

export default function (pi: ExtensionAPI) {
	// The skill runs `robot-voice <command>`; put the CLI on the PATH that pi's
	// bash tool inherits, like Claude Code does with a plugin's bin/.
	const bin = path.join(ROOT, "bin");
	if (!(process.env.PATH || "").split(path.delimiter).includes(bin)) {
		process.env.PATH = `${bin}${path.delimiter}${process.env.PATH || ""}`;
	}

	let pending = "";

	pi.on("session_start", async (_event, ctx) => {
		session(ctx);
	});

	// agent_end fires after each low-level run; pi may still retry, compact or
	// continue. Keep the reply, and speak it once the whole run has settled.
	pi.on("agent_end", async (event) => {
		pending = replyText(event.messages ?? []);
	});

	pi.on("agent_settled", async (_event, ctx) => {
		const text = pending;
		pending = "";
		// The interactive TUI only: `pi -p` in a script should stay quiet.
		if (!text.trim() || ctx.mode !== "tui") return;
		speak(text, session(ctx));
	});

	// /robot:use, :voice, :all, :tldr, :brief, :help -- the same commands as
	// Claude Code's /robot-voice:<name>. Each runs locally, without the model.
	for (const [name, description] of Object.entries(COMMANDS)) {
		pi.registerCommand(`robot:${name}`, {
			description,
			handler: async (args, ctx) => {
				const request = args.trim();
				const argv = ["-m", "robot_voice", "--detach", "--shortcut", name,
					"--prefix", "/robot:", "--session", session(ctx),
					...(request ? request.split(/\s+/) : [])];
				const failed = await new Promise<boolean>((resolve) => {
					execFile(PYTHON, argv, { cwd: ROOT, env: env(), timeout: 15000 },
						(err, stdout, stderr) => {
							if (err && name === "use" && request) return resolve(true);
							const out = (stdout || "").trim() || (stderr || "").trim()
								|| (err ? String(err.message) : "done");
							ctx.ui.notify(out, err ? "error" : "info");
							resolve(false);
						});
				});
				if (!failed) return;
				// /robot:use in plain words ("a female Portuguese voice"): hand it
				// to the agent through the skill, like Claude Code does.
				pi.sendUserMessage(`/skill:robot-voice ${request}`, {
					expandPromptTemplates: true,
					...(ctx.isIdle() ? {} : { deliverAs: "followUp" as const }),
				});
			},
		});
	}
}
