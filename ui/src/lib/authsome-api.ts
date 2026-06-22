export type DashboardStats = {
  connected: number;
  available: number;
  oauth: number;
  apiKey: number;
};

export type ProviderView = {
  name: string;
  displayName: string;
  definition: ProviderResponse;
  authType: "oauth2" | "api_key" | string;
  authTypeLabel: string;
  providerType: "app" | "llm" | "mcp" | "browser" | null;
  apiUrl: string;
  description: string;
  source: "bundled" | "custom" | string;
  logo: string | null;
  logoInitial: string;
  status: "available" | "connected" | "reauth" | string;
  scopeCount: number;
  connectionCount: number;
  globalConnectionCount: number;
};

export type ConnectionRow = {
  providerName: string;
  providerDisplayName: string;
  connectionName: string;
  status: string;
  authTypeLabel: string;
};

export type GlobalConnectionRow = ConnectionRow & {
  accountLabel: string | null;
};

export type AgentRow = {
  handle: string;
  isActive: boolean;
  claimStatus: string;
};

export type AuditRow = {
  eventId: string;
  time: string;
  eventName: string;
  event: string;
  source: string;
  actor: string;
  target: string;
  status: string;
  metadata: Record<string, unknown>;
};

export type AuditEventsQuery = {
  cursor?: string | null;
  identity?: string | null;
  limit?: number;
};

export type AuditEventsData = {
  scope: "global" | "principal";
  nextCursor: string | null;
  events: AuditRow[];
  total: number;
};

export type DashboardData = {
  version: string;
  account: {
    email: string | null;
    roleLabel: string | null;
    isAdmin: boolean;
    principalId: string | null;
    agent: string | null;
  };
  stats: DashboardStats;
  latestTokenExpiry: string;
  providers: ProviderView[];
  connectedProviders: ProviderView[];
  connections: ConnectionRow[];
  globalConnections: GlobalConnectionRow[];
  agents: AgentRow[];
  vault: {
    vaultId: string | null;
    handle: string;
    isDefault: boolean;
  };
  audit: {
    canView: boolean;
    scope: "global" | "principal";
    nextCursor: string | null;
    total: number;
    events: AuditRow[];
  };
};

export type AgentDetail = {
  handle: string;
  did: string;
  registration_status: string;
  claim_status: string | null;
  principal_id: string | null;
  principal_email: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  claimed_at: string | null;
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

type GlobalConnectionSummary = {
  provider: string;
  provider_display_name: string;
  connection_name: string;
  status: string;
  auth_type: string;
  account_label: string | null;
  api_url?: string | null;
  source: "global";
};

export type ProviderResponse = {
  name: string;
  display_name?: string;
  logo?: string | null;
  description?: string | null;
  type?: "app" | "llm" | "mcp" | "browser" | string | null;
  auth_type?: string;
  flow?: string;
  api_url?: string | string[] | null;
  oauth?: {
    authorization_url?: string;
    token_url?: string;
    revocation_url?: string | null;
    device_authorization_url?: string | null;
    device_token_request?: "oauth2_form" | "json";
    scopes?: string[];
    authorization_params?: Record<string, string>;
    pkce?: boolean;
    supports_device_code?: boolean;
    supports_dcr?: boolean;
    base_url?: string | null;
    authorization_method?: "body" | "basic";
  } | null;
  registration?: {
    registration_endpoint?: string | null;
  } | null;
  api_key?: {
    header_name?: string;
    header_prefix?: string | null;
    key_pattern?: string | null;
    key_pattern_hint?: string | null;
  } | null;
  browser?: {
    entry_url?: string;
    domains?: string[];
    auth_cookies?: string[];
    validate_url?: string | null;
    extra_headers?: Record<string, string>;
    ttl_hours?: number;
    ttl_from_cookie?: string | null;
    extract?: Array<{
      cookie: string;
      header: string;
      prefix?: string;
    }>;
  } | null;
  export?: Record<string, string> | { env?: Record<string, string> } | null;
  metadata?: {
    description?: string;
  };
  docs_url?: string | null;
};

export type ProviderDefinitionPayload = {
  schema_version?: number;
  name: string;
  display_name: string;
  logo?: string | null;
  description?: string | null;
  type?: "app" | "llm" | "mcp" | "browser" | null;
  auth_type: "oauth2" | "api_key" | "browser";
  flow: "pkce" | "device_code" | "dcr_pkce" | "api_key" | "browser";
  oauth?: NonNullable<ProviderResponse["oauth"]> | null;
  registration?: NonNullable<ProviderResponse["registration"]> | null;
  api_key?: NonNullable<ProviderResponse["api_key"]> | null;
  browser?: NonNullable<ProviderResponse["browser"]> | null;
  export?: ProviderResponse["export"];
  docs_url?: string | null;
  api_url?: string | string[] | null;
  metadata?: Record<string, unknown>;
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
  can_set_global: boolean;
  is_global: boolean;
};

type ConnectionsResponse = {
  connections: Array<{
    name: string;
    connections: ConnectionSummary[];
  }>;
  global_connections: GlobalConnectionSummary[];
  provider_connection_counts: Record<string, number>;
  by_source: Record<string, ProviderResponse[]>;
};

type AuditResponse = {
  entries: Array<Record<string, unknown>>;
  next_cursor?: string | null;
  scope?: "global" | "principal";
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

function providerStatus(connections: ConnectionSummary[], globalConnections: GlobalConnectionSummary[]): ProviderView["status"] {
  if (!connections.length && !globalConnections.length) {
    return "available";
  }
  return [...connections, ...globalConnections].some((connection) => ["error", "expired"].includes(connection.status || ""))
    ? "reauth"
    : "connected";
}

function providerView(
  provider: ProviderResponse,
  source: string,
  connections: ConnectionSummary[],
  globalConnections: GlobalConnectionSummary[],
  providerConnectionCount?: number,
): ProviderView {
  const displayName = provider.display_name || provider.name;
  const localConnectionCount = connections.length + globalConnections.length;
  const connectionCount = providerConnectionCount ?? localConnectionCount;
  return {
    name: provider.name,
    displayName,
    definition: provider,
    authType: provider.auth_type || "provider",
    authTypeLabel: authTypeLabel(provider.auth_type),
    providerType: (provider.type as ProviderView["providerType"]) || null,
    apiUrl: providerApiUrl(provider),
    description: provider.description || provider.metadata?.description || "",
    source,
    logo: provider.logo || null,
    logoInitial: (displayName[0] || "?").toUpperCase(),
    status: providerConnectionCount && providerConnectionCount > 0 ? "connected" : providerStatus(connections, globalConnections),
    scopeCount: connections[0]?.scopes?.length || 0,
    connectionCount,
    globalConnectionCount: globalConnections.length,
  };
}

function buildProviders(data: ConnectionsResponse): ProviderView[] {
  const connectionMap = new Map(data.connections.map((group) => [group.name, group.connections]));
  const providerConnectionCounts = data.provider_connection_counts || {};
  const globalConnectionMap = new Map<string, GlobalConnectionSummary[]>();
  for (const connection of data.global_connections || []) {
    const entries = globalConnectionMap.get(connection.provider) || [];
    entries.push(connection);
    globalConnectionMap.set(connection.provider, entries);
  }
  return Object.entries(data.by_source).flatMap(([source, providers]) =>
    providers.map((provider) =>
      providerView(
        provider,
        source,
        connectionMap.get(provider.name) || [],
        globalConnectionMap.get(provider.name) || [],
        providerConnectionCounts[provider.name],
      ),
    ),
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

function buildGlobalConnectionRows(data: ConnectionsResponse): GlobalConnectionRow[] {
  return (data.global_connections || [])
    .map((connection) => ({
      providerName: connection.provider,
      providerDisplayName: connection.provider_display_name,
      connectionName: connection.connection_name,
      status: connection.status || "unknown",
      authTypeLabel: authTypeLabel(connection.auth_type),
      accountLabel: connection.account_label,
    }))
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

function latestTokenExpiry(data: ConnectionsResponse): string {
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
      eventName: String(entry.event || "audit_event"),
      event: humanize(entry.event),
      source: String(entry.source || "internal"),
      actor: String(entry.identity || entry.principal_id || "system"),
      target: [provider, connection].filter(Boolean).join(" / ") || "Authsome",
      status: String(entry.status || "-"),
      metadata,
    };
  });
}

function auditQueryString(query: AuditEventsQuery = {}): string {
  const params = new URLSearchParams();
  params.set("limit", String(query.limit ?? 50));
  if (query.cursor) params.set("cursor", query.cursor);
  if (query.identity) params.set("identity", query.identity);
  return params.toString();
}

export async function fetchAuditEvents(query: AuditEventsQuery = {}): Promise<AuditEventsData> {
  const data = await requestJson<AuditResponse>(`/api/audit/events?${auditQueryString(query)}`);
  const events = buildAuditRows(data.entries);
  return {
    scope: data.scope ?? "principal",
    nextCursor: data.next_cursor ?? null,
    events,
    total: events.length,
  };
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
  const audit = await fetchAuditEvents({ limit: 100 });
  const providers = buildProviders(connectionsData);
  const connections = buildConnectionRows(connectionsData, providers);
  const globalConnections = buildGlobalConnectionRows(connectionsData);
  const connectedProviders = providers.filter((provider) => provider.status !== "available");
  const activeAgent = whoami.identity || whoami.active_identity || null;
  const identityStatusMap = new Map(identitiesData.identities.map((identity) => [identity.handle, identity.status || "accepted"]));
  if (activeAgent && !identityStatusMap.has(activeAgent)) {
    identityStatusMap.set(activeAgent, "accepted");
  }

  return {
    version: whoami.version,
    account: {
      email: whoami.account_email || null,
      roleLabel: roleLabel(whoami.principal_role),
      isAdmin,
      principalId: whoami.principal_id || null,
      agent: activeAgent,
    },
    stats: {
      connected: connectedProviders.length,
      available: providers.length - connectedProviders.length,
      oauth: connectedProviders.filter((provider) => provider.authType === "oauth2").length,
      apiKey: connectedProviders.filter((provider) => provider.authType === "api_key").length,
    },
    latestTokenExpiry: latestTokenExpiry(connectionsData),
    providers,
    connectedProviders: connectedProviders.slice(0, 6),
    connections,
    globalConnections,
    agents: Array.from(identityStatusMap, ([handle, claimStatus]) => ({ handle, isActive: handle === activeAgent, claimStatus })),
    vault: {
      vaultId: whoami.vault_id || null,
      handle: "default",
      isDefault: true,
    },
    audit: {
      canView: true,
      scope: audit.scope,
      nextCursor: audit.nextCursor,
      total: audit.total,
      events: audit.events,
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

export async function fetchAgentDetail(agent: string): Promise<AgentDetail> {
  return requestJson<AgentDetail>(`/api/identities/${encodeURIComponent(agent)}/detail`);
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

export async function createCustomProvider(
  definition: ProviderDefinitionPayload,
): Promise<{ status: "ok"; provider: string }> {
  return sendJson("/api/providers", {
    method: "POST",
    body: JSON.stringify({ definition }),
  });
}

export async function updateCustomProvider(
  provider: string,
  definition: ProviderDefinitionPayload,
): Promise<{ status: "ok"; provider: string }> {
  return sendJson(`/api/providers/${encodeURIComponent(provider)}`, {
    method: "PUT",
    body: JSON.stringify({ definition }),
  });
}

export async function deleteCustomProvider(provider: string): Promise<{ status: "ok"; provider: string }> {
  return sendJson(`/api/providers/${encodeURIComponent(provider)}`, {
    method: "DELETE",
    body: "{}",
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

export async function setGlobalConnection(
  provider: string,
  connection: string,
): Promise<{ status: string; provider: string; connection_name: string }> {
  return sendJson(`/api/connections/${encodeURIComponent(provider)}/${encodeURIComponent(connection)}/global`, {
    method: "POST",
    body: "{}",
  });
}

export async function unsetGlobalConnection(provider: string): Promise<{ status: string; provider: string; deleted: boolean }> {
  return sendJson(`/api/connections/${encodeURIComponent(provider)}/global`, {
    method: "DELETE",
    body: "{}",
  });
}

export async function revokeProvider(provider: string): Promise<{ status: string; provider?: string }> {
  return sendJson(`/api/connections/${encodeURIComponent(provider)}/revoke`, {
    method: "POST",
    body: "{}",
  });
}
