import "server-only";

type Environment = Record<string, string | undefined>;

const serverSecretNames = [
  "WEB_ADMIN_PASSWORD_HASH",
  "WEB_SESSION_SECRET",
  "SUPABASE_SECRET_KEY",
  "GITHUB_ACTIONS_TOKEN",
] as const;

export class ServerEnvironmentError extends Error {}

export type ServerEnvironment = Readonly<{
  adminPasswordHash: string | undefined;
  sessionSecret: string | undefined;
  supabaseUrl: string | undefined;
  supabaseSecretKey: string | undefined;
  githubActionsToken: string | undefined;
  githubRepositoryOwner: string | undefined;
  githubRepositoryName: string | undefined;
  githubWorkflowFile: string | undefined;
}>;

function readOptional(environment: Environment, name: string): string | undefined {
  const value = environment[name]?.trim();
  return value ? value : undefined;
}

function requireProductionValue(environment: Environment, name: string): string {
  const value = readOptional(environment, name);
  if (!value) {
    throw new ServerEnvironmentError(`${name} é obrigatória em produção`);
  }
  return value;
}

export function readServerEnvironment(environment: Environment = process.env): ServerEnvironment {
  for (const secretName of serverSecretNames) {
    if (readOptional(environment, `NEXT_PUBLIC_${secretName}`)) {
      throw new ServerEnvironmentError(`${secretName} não pode usar prefixo NEXT_PUBLIC_`);
    }
  }

  const production = environment.NODE_ENV === "production";
  const adminPasswordHash = production
    ? requireProductionValue(environment, "WEB_ADMIN_PASSWORD_HASH")
    : readOptional(environment, "WEB_ADMIN_PASSWORD_HASH");
  const sessionSecret = production
    ? requireProductionValue(environment, "WEB_SESSION_SECRET")
    : readOptional(environment, "WEB_SESSION_SECRET");

  if (sessionSecret && new TextEncoder().encode(sessionSecret).byteLength < 32) {
    throw new ServerEnvironmentError("WEB_SESSION_SECRET deve ter ao menos 32 bytes");
  }

  return {
    adminPasswordHash,
    sessionSecret,
    supabaseUrl: readOptional(environment, "SUPABASE_URL"),
    supabaseSecretKey: readOptional(environment, "SUPABASE_SECRET_KEY"),
    githubActionsToken: readOptional(environment, "GITHUB_ACTIONS_TOKEN"),
    githubRepositoryOwner: readOptional(environment, "GITHUB_REPOSITORY_OWNER"),
    githubRepositoryName: readOptional(environment, "GITHUB_REPOSITORY_NAME"),
    githubWorkflowFile: readOptional(environment, "GITHUB_WORKFLOW_FILE"),
  };
}
