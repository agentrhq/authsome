export type DashboardStats = {
  connected: number;
  available: number;
  oauth: number;
  apiKey: number;
};

export type ProviderView = {
  name: string;
  displayName: string;
  authType: "oauth2" | "api_key" | string;
  authTypeLabel: string;
  apiUrl: string;
  description: string;
  source: "bundled" | "custom" | string;
  logo: string | null;
  logoInitial: string;
  status: "available" | "connected" | "reauth" | string;
  scopeCount: number;
  connectionCount: number;
  requiresNamedLogin: boolean;
};

export type ConnectionRow = {
  providerName: string;
  providerDisplayName: string;
  connectionName: string;
  status: string;
  authTypeLabel: string;
};

export type IdentityRow = {
  handle: string;
  isActive: boolean;
};

export type AuditRow = {
  eventId: string;
  time: string;
  event: string;
  source: string;
  actor: string;
  target: string;
  status: string;
  metadata: Record<string, unknown>;
};

export type DashboardData = {
  version: string;
  account: {
    email: string | null;
    roleLabel: string | null;
    isAdmin: boolean;
    principalId: string | null;
    identity: string | null;
  };
  stats: DashboardStats;
  lastActivity: string;
  providers: ProviderView[];
  connectedProviders: ProviderView[];
  connections: ConnectionRow[];
  identities: IdentityRow[];
  vault: {
    vaultId: string | null;
    handle: string;
    isDefault: boolean;
  };
  audit: {
    canView: boolean;
    total: number;
    events: AuditRow[];
  };
};

type WhoamiResponse = {
  version: string;
  identity?: string;
  active_identity?: string;
  principal_id?: string;
  principal_role?: string;
  account_email?: string;
  vault_id?: string;
};

type IdentitiesResponse = {
  identities: Array<{
    handle: string;
    status?: string;
  }>;
};

type ConnectionSummary = {
  connection_name: string;
  auth_type?: string;
  status?: string;
  scopes?: string[];
  expires_at?: string | null;
};

export type ProviderResponse = {
  name: string;
  display_name?: string;
  logo?: string | null;
  description?: string | null;
  auth_type?: string;
  api_url?: string | string[] | null;
  oauth?: {
    base_url?: string | null;
  } | null;
  metadata?: {
    description?: string;
  };
  docs_url?: string | null;
};

export type ProviderClientDetail = {
  client_id: string | null;
  client_secret: string | null;
  base_url: string | null;
  api_url: string | null;
  scopes: string[];
};

export type ProviderConfigurationField = {
  name: string;
  label: string;
  secret: boolean;
  default?: string | null;
  pattern?: string | null;
  pattern_hint?: string | null;
};

export type ProviderConnectionSummary = {
  provider: string;
  provider_display_name: string;
  connection_name: string;
  status: string;
  auth_type: string;
  account_label: string | null;
  principal_id: string | null;
};

export type ProviderPrincipalUsage = {
  principal_id: string;
  email: string | null;
  connections: ProviderConnectionSummary[];
};

export type ProviderDetail = {
  provider: ProviderResponse;
  account: {
    principal_id: string | null;
    role: string;
    is_admin: boolean;
  };
  client: ProviderClientDetail | null;
  configuration_fields: ProviderConfigurationField[];
  configuration_warning: string | null;
  show_callback_helper: boolean;
  callback_url: string | null;
  connections: ProviderConnectionSummary[];
  principal_usage: ProviderPrincipalUsage[];
};

export type ConnectionDetail = {
  provider: string;
  provider_display_name: string;
  connection_name: string;
  principal_id: string | null;
  identity: string | null;
  vault_id: string | null;
  status: string;
  auth_type: string;
  base_url: string | null;
  api_url: string | null;
  scopes: string[];
  token_type: string | null;
  obtained_at: string | null;
  expires_at: string | null;
  account: Record<string, unknown> | null;
  secrets: {
    access_token: string | null;
    refresh_token: string | null;
    api_key: string | null;
    credentials: Record<string, string>;
  };
  can_set_default: boolean;
};

type ConnectionsResponse = {
  connections: Array<{
    name: string;
    connections: ConnectionSummary[];
  }>;
  by_source: Record<string, ProviderResponse[]>;
};

type AuditResponse = {
  entries: Array<Record<string, unknown>>;
};

export type PrincipalRow = {
  principal_id: string;
  email: string;
  role: string;
  created_at: string;
};

export type ClaimStatus = {
  token: string;
  identity: string;
  authenticated: boolean;
  email?: string;
  expired: boolean;
};

export type SessionInputField = {
  name: string;
  label: string;
  secret: boolean;
  default?: string | null;
  required?: boolean;
  pattern?: string | null;
  pattern_hint?: string | null;
};

export type SessionInputData = {
  session_id: string;
  provider: string;
  display_name: string;
  docs_url?: string | null;
  fields: SessionInputField[];
  callback_url?: string | null;
  warning?: string | null;
};

export type SessionDeviceData = {
  session_id: string;
  display_name: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete?: string | null;
};

export type AuthSessionStatus = {
  id: string;
  provider: string;
  connection: string;
  status: string;
  message?: string | null;
  error?: string | null;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let message = response.statusText || "Request failed";
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      message = payload.detail || payload.message || message;
    } catch {
      // Status is sufficient for the UI's failure modes.
    }
    throw new ApiError(response.status, message);
  }

  return response.json() as Promise<T>;
}

async function sendJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = response.statusText || "Request failed";
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      message = payload.detail || payload.message || message;
    } catch {
      // Status is sufficient for the UI's failure modes.
    }
    throw new ApiError(response.status, message);
  }

  return response.json() as Promise<T>;
}

function authTypeLabel(authType?: string): string {
  return authType === "oauth2" ? "OAuth 2.0" : authType === "api_key" ? "API Key" : authType || "Provider";
}

function providerApiUrl(provider: ProviderResponse): string {
  if (Array.isArray(provider.api_url)) {
    return provider.api_url.filter(Boolean).join(", ") || provider.name;
  }
  return provider.api_url || provider.oauth?.base_url || provider.name;
}

function providerStatus(connections: ConnectionSummary[]): ProviderView["status"] {
  if (!connections.length) {
    return "available";
  }
  return connections.some((connection) => ["error", "expired"].includes(connection.status || ""))
    ? "reauth"
    : "connected";
}

function providerView(
  provider: ProviderResponse,
  source: string,
  connections: ConnectionSummary[],
): ProviderView {
  const displayName = provider.display_name || provider.name;
  return {
    name: provider.name,
    displayName,
    authType: provider.auth_type || "provider",
    authTypeLabel: authTypeLabel(provider.auth_type),
    apiUrl: providerApiUrl(provider),
    description: provider.description || provider.metadata?.description || "",
    source,
    logo: provider.logo || null,
    logoInitial: (displayName[0] || "?").toUpperCase(),
    status: providerStatus(connections),
    scopeCount: connections[0]?.scopes?.length || 0,
    connectionCount: connections.length,
    requiresNamedLogin: connections.some((connection) => connection.connection_name === "default"),
  };
}

function buildProviders(data: ConnectionsResponse): ProviderView[] {
  const connectionMap = new Map(data.connections.map((group) => [group.name, group.connections]));
  return Object.entries(data.by_source).flatMap(([source, providers]) =>
    providers.map((provider) => providerView(provider, source, connectionMap.get(provider.name) || [])),
  );
}

function buildConnectionRows(data: ConnectionsResponse, providers: ProviderView[]): ConnectionRow[] {
  const providerMap = new Map(providers.map((provider) => [provider.name, provider]));
  return data.connections
    .flatMap((group) => {
      const provider = providerMap.get(group.name);
      return group.connections.map((connection) => ({
        providerName: group.name,
        providerDisplayName: provider?.displayName || group.name,
        connectionName: connection.connection_name,
        status: connection.status || "unknown",
        authTypeLabel: authTypeLabel(connection.auth_type || provider?.authType),
      }));
    })
    .sort((a, b) => `${a.providerDisplayName}:${a.connectionName}`.localeCompare(`${b.providerDisplayName}:${b.connectionName}`));
}

function formatRelative(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return null;
  }
  const deltaSeconds = Math.round((parsed.valueOf() - Date.now()) / 1000);
  const absSeconds = Math.abs(deltaSeconds);
  const direction = deltaSeconds >= 0 ? "in" : "ago";
  const units: Array<[number, string]> = [
    [86_400, "day"],
    [3_600, "hour"],
    [60, "minute"],
    [1, "second"],
  ];
  const [unitSeconds, unit] = units.find(([seconds]) => absSeconds >= seconds) || [1, "second"];
  const amount = Math.max(1, Math.floor(absSeconds / unitSeconds));
  const label = `${amount} ${unit}${amount === 1 ? "" : "s"}`;
  return direction === "in" ? `in ${label}` : `${label} ago`;
}

function lastActivity(data: ConnectionsResponse): string {
  const latest = data.connections
    .flatMap((group) => group.connections)
    .map((connection) => connection.expires_at)
    .filter((value): value is string => Boolean(value))
    .sort((a, b) => new Date(b).valueOf() - new Date(a).valueOf())[0];
  return formatRelative(latest) || "-";
}

function humanize(value: unknown): string {
  const event = String(value || "audit_event").replaceAll("_", " ").replaceAll("-", " ").trim();
  return event ? event[0].toUpperCase() + event.slice(1) : "Audit event";
}

function formatAuditTime(value: unknown): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(String(value));
  if (Number.isNaN(parsed.valueOf())) {
    return String(value);
  }
  return parsed.toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

function buildAuditRows(entries: AuditResponse["entries"]): AuditRow[] {
  const known = new Set(["event_id", "timestamp", "event", "source", "principal_id", "identity", "provider", "connection", "status"]);
  return entries.map((entry, index) => {
    const provider = entry.provider ? String(entry.provider) : "";
    const connection = entry.connection ? String(entry.connection) : "";
    const metadata = Object.fromEntries(Object.entries(entry).filter(([key, value]) => !known.has(key) && value != null));
    return {
      eventId: String(entry.event_id || `${entry.timestamp || "event"}-${index}`),
      time: formatAuditTime(entry.timestamp),
      event: humanize(entry.event),
      source: String(entry.source || "internal"),
      actor: String(entry.identity || entry.principal_id || "system"),
      target: [provider, connection].filter(Boolean).join(" / ") || "Authsome",
      status: String(entry.status || "-"),
      metadata,
    };
  });
}

function roleLabel(role: string | undefined): string | null {
  if (!role) {
    return null;
  }
  return role.slice(0, 1).toUpperCase() + role.slice(1);
}

export async function fetchDashboard(): Promise<DashboardData> {
  const [whoami, identitiesData, connectionsData] = await Promise.all([
    requestJson<WhoamiResponse>("/api/whoami"),
    requestJson<IdentitiesResponse>("/api/identities"),
    requestJson<ConnectionsResponse>("/api/connections"),
  ]);
  const isAdmin = whoami.principal_role === "admin";
  const audit = isAdmin ? await requestJson<AuditResponse>("/api/audit/events?limit=100") : { entries: [] };
  const providers = buildProviders(connectionsData);
  const connections = buildConnectionRows(connectionsData, providers);
  const connectedProviders = providers.filter((provider) => provider.status !== "available");
  const activeIdentity = whoami.identity || whoami.active_identity || null;
  const identityHandles = new Set(identitiesData.identities.map((identity) => identity.handle));
  if (activeIdentity) {
    identityHandles.add(activeIdentity);
  }

  return {
    version: whoami.version,
    account: {
      email: whoami.account_email || null,
      roleLabel: roleLabel(whoami.principal_role),
      isAdmin,
      principalId: whoami.principal_id || null,
      identity: activeIdentity,
    },
    stats: {
      connected: connectedProviders.length,
      available: providers.length - connectedProviders.length,
      oauth: connectedProviders.filter((provider) => provider.authType === "oauth2").length,
      apiKey: connectedProviders.filter((provider) => provider.authType === "api_key").length,
    },
    lastActivity: lastActivity(connectionsData),
    providers,
    connectedProviders: connectedProviders.slice(0, 6),
    connections,
    identities: Array.from(identityHandles, (handle) => ({ handle, isActive: handle === activeIdentity })),
    vault: {
      vaultId: whoami.vault_id || null,
      handle: "default",
      isDefault: true,
    },
    audit: {
      canView: isAdmin,
      total: audit.entries.length,
      events: buildAuditRows(audit.entries),
    },
  };
}

export async function fetchPrincipals(): Promise<PrincipalRow[]> {
  const data = await requestJson<{ principals: PrincipalRow[] }>("/api/principals");
  return data.principals;
}

export async function fetchClaimStatus(token: string): Promise<ClaimStatus> {
  return requestJson<ClaimStatus>(`/api/claim/${encodeURIComponent(token)}`);
}

export async function fetchSessionInput(sessionId: string): Promise<SessionInputData> {
  return requestJson<SessionInputData>(`/api/auth/sessions/${encodeURIComponent(sessionId)}/input`);
}

export async function fetchSessionDevice(sessionId: string): Promise<SessionDeviceData> {
  return requestJson<SessionDeviceData>(`/api/auth/sessions/${encodeURIComponent(sessionId)}/device`);
}

export async function fetchAuthSessionStatus(sessionId: string): Promise<AuthSessionStatus> {
  return requestJson<AuthSessionStatus>(`/api/auth/sessions/${encodeURIComponent(sessionId)}/status`);
}

export async function fetchProviderDetail(provider: string): Promise<ProviderDetail> {
  return requestJson<ProviderDetail>(`/api/providers/${encodeURIComponent(provider)}/detail`);
}

export async function updateProviderConfiguration(
  provider: string,
  payload: Record<string, string | undefined>,
): Promise<{ status: "ok"; changed: boolean; provider: string }> {
  return sendJson(`/api/providers/${encodeURIComponent(provider)}/configuration`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function fetchConnectionDetail(
  provider: string,
  connection: string,
  principal?: string,
): Promise<ConnectionDetail> {
  const query = principal ? `?principal=${encodeURIComponent(principal)}` : "";
  return requestJson<ConnectionDetail>(
    `/api/connections/${encodeURIComponent(provider)}/${encodeURIComponent(connection)}/detail${query}`,
  );
}

export async function logoutConnection(
  provider: string,
  connection: string,
  principal?: string,
): Promise<{ status: string }> {
  const query = principal ? `?principal=${encodeURIComponent(principal)}` : "";
  return sendJson(`/api/connections/${encodeURIComponent(provider)}/${encodeURIComponent(connection)}/logout${query}`, {
    method: "POST",
    body: "{}",
  });
}

export async function revokeProvider(provider: string): Promise<{ status: string; provider?: string }> {
  return sendJson(`/api/connections/${encodeURIComponent(provider)}/revoke`, {
    method: "POST",
    body: "{}",
  });
}
