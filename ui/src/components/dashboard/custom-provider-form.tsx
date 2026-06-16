"use client";

import { Plus, Save, Trash2 } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  ApiError,
  ProviderDefinitionPayload,
  ProviderResponse,
  createCustomProvider,
  updateCustomProvider,
} from "@/lib/authsome-api";
import { cn } from "@/lib/utils";

type AuthType = "oauth2" | "api_key" | "browser";
type FlowType = "pkce" | "device_code" | "dcr_pkce" | "api_key" | "browser";
type ProviderType = "app" | "llm" | "mcp" | "browser";

type KeyValueRow = {
  id: string;
  key: string;
  value: string;
};

type ExtractRow = {
  id: string;
  cookie: string;
  header: string;
  prefix: string;
};

type FieldKey =
  | "name"
  | "displayName"
  | "apiTargets"
  | "docsUrl"
  | "oauthBaseUrl"
  | "oauthAuthorizationUrl"
  | "oauthTokenUrl"
  | "oauthRevocationUrl"
  | "oauthDeviceAuthorizationUrl"
  | "registrationEndpoint"
  | "browserEntryUrl"
  | "browserValidateUrl"
  | "browserTtlHours";

type FieldErrors = Partial<Record<FieldKey, string>>;

type ValidationResult = {
  field: FieldKey;
  message: string;
};

type ProviderFormState = {
  name: string;
  displayName: string;
  logo: string;
  description: string;
  providerType: ProviderType;
  authType: AuthType;
  flow: FlowType;
  apiTargets: string[];
  docsUrl: string;
  oauth: {
    authorizationUrl: string;
    tokenUrl: string;
    revocationUrl: string;
    deviceAuthorizationUrl: string;
    deviceTokenRequest: "oauth2_form" | "json";
    scopes: string[];
    authorizationParams: KeyValueRow[];
    pkce: boolean;
    supportsDeviceCode: boolean;
    supportsDcr: boolean;
    baseUrl: string;
    authorizationMethod: "body" | "basic";
  };
  registrationEndpoint: string;
  apiKey: {
    headerName: string;
    headerPrefixMode: "Bearer" | "Basic" | "Token" | "empty" | "none" | "custom";
    headerPrefixCustom: string;
    keyPattern: string;
    keyPatternHint: string;
  };
  browser: {
    entryUrl: string;
    domains: string[];
    authCookies: string[];
    validateUrl: string;
    ttlHours: string;
    ttlFromCookie: string;
    extraHeaders: KeyValueRow[];
    extract: ExtractRow[];
  };
  exportRows: KeyValueRow[];
};

const FLOW_OPTIONS: Record<AuthType, Array<{ value: FlowType; label: string }>> = {
  oauth2: [
    { value: "pkce", label: "PKCE" },
    { value: "device_code", label: "Device code" },
    { value: "dcr_pkce", label: "DCR + PKCE" },
  ],
  api_key: [{ value: "api_key", label: "API key" }],
  browser: [{ value: "browser", label: "Browser session" }],
};

const AUTH_TYPES: Array<{ value: AuthType; label: string }> = [
  { value: "oauth2", label: "OAuth 2.0" },
  { value: "api_key", label: "API key" },
  { value: "browser", label: "Browser session" },
];

const PROVIDER_TYPES: Array<{ value: ProviderType; label: string }> = [
  { value: "app", label: "App" },
  { value: "llm", label: "LLM" },
  { value: "mcp", label: "MCP" },
  { value: "browser", label: "Browser" },
];

function rowId(): string {
  return Math.random().toString(36).slice(2);
}

function kvRows(record: Record<string, string> | undefined): KeyValueRow[] {
  return Object.entries(record || {}).map(([key, value]) => ({ id: rowId(), key, value }));
}

function splitList(values: string[] | undefined): string[] {
  return values?.length ? values : [""];
}

function headerPrefixState(value: string | null | undefined): ProviderFormState["apiKey"] {
  const base = {
    headerName: "Authorization",
    headerPrefixMode: "Bearer" as const,
    headerPrefixCustom: "",
    keyPattern: "",
    keyPatternHint: "",
  };
  if (value === null) return { ...base, headerPrefixMode: "none" };
  if (value === "") return { ...base, headerPrefixMode: "empty" };
  if (value === "Bearer" || value === "Basic" || value === "Token") {
    return { ...base, headerPrefixMode: value };
  }
  if (value) return { ...base, headerPrefixMode: "custom", headerPrefixCustom: value };
  return base;
}

function initialState(provider?: ProviderResponse | null): ProviderFormState {
  const authType = (provider?.auth_type as AuthType | undefined) || "oauth2";
  const defaultFlow = FLOW_OPTIONS[authType][0].value;
  const apiKeyState = headerPrefixState(provider?.api_key?.header_prefix);
  const exportRecord = provider?.export && "env" in provider.export ? provider.export.env : provider?.export;
  return {
    name: provider?.name || "",
    displayName: provider?.display_name || "",
    logo: provider?.logo || "",
    description: provider?.description || provider?.metadata?.description || "",
    providerType: (provider?.type as ProviderType | undefined) || "app",
    authType,
    flow: (provider?.flow as FlowType | undefined) || defaultFlow,
    apiTargets: splitList(
      Array.isArray(provider?.api_url)
        ? provider?.api_url
        : provider?.api_url
          ? [provider.api_url]
          : undefined,
    ),
    docsUrl: provider?.docs_url || "",
    oauth: {
      authorizationUrl: provider?.oauth?.authorization_url || "",
      tokenUrl: provider?.oauth?.token_url || "",
      revocationUrl: provider?.oauth?.revocation_url || "",
      deviceAuthorizationUrl: provider?.oauth?.device_authorization_url || "",
      deviceTokenRequest: provider?.oauth?.device_token_request || "oauth2_form",
      scopes: splitList(provider?.oauth?.scopes),
      authorizationParams: kvRows(provider?.oauth?.authorization_params),
      pkce: provider?.oauth?.pkce ?? true,
      supportsDeviceCode: provider?.oauth?.supports_device_code ?? false,
      supportsDcr: provider?.oauth?.supports_dcr ?? false,
      baseUrl: provider?.oauth?.base_url || "",
      authorizationMethod: provider?.oauth?.authorization_method || "body",
    },
    registrationEndpoint: provider?.registration?.registration_endpoint || "",
    apiKey: {
      ...apiKeyState,
      headerName: provider?.api_key?.header_name || "Authorization",
      keyPattern: provider?.api_key?.key_pattern || "",
      keyPatternHint: provider?.api_key?.key_pattern_hint || "",
    },
    browser: {
      entryUrl: provider?.browser?.entry_url || "",
      domains: splitList(provider?.browser?.domains),
      authCookies: splitList(provider?.browser?.auth_cookies),
      validateUrl: provider?.browser?.validate_url || "",
      ttlHours: String(provider?.browser?.ttl_hours || 24),
      ttlFromCookie: provider?.browser?.ttl_from_cookie || "",
      extraHeaders: kvRows(provider?.browser?.extra_headers),
      extract: (provider?.browser?.extract || []).map((row) => ({
        id: rowId(),
        cookie: row.cookie,
        header: row.header,
        prefix: row.prefix || "",
      })),
    },
    exportRows: kvRows(exportRecord && !Array.isArray(exportRecord) ? exportRecord as Record<string, string> : {}),
  };
}

function cleanList(values: string[]): string[] {
  return values.map((value) => value.trim()).filter(Boolean);
}

function cleanRecord(rows: KeyValueRow[]): Record<string, string> {
  return Object.fromEntries(
    rows
      .map((row) => [row.key.trim(), row.value.trim()] as const)
      .filter(([key]) => Boolean(key)),
  );
}

function isHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function isTemplateUrl(value: string, baseUrl: string): boolean {
  return value.includes("{base_url}") && Boolean(baseUrl.trim()) && isHttpUrl(baseUrl.trim());
}

function isApiTarget(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed || /\s/.test(trimmed)) return false;
  if (trimmed.startsWith("regex:")) {
    try {
      new RegExp(trimmed.slice("regex:".length));
      return true;
    } catch {
      return false;
    }
  }
  return isHttpUrl(trimmed) || isHttpUrl(`https://${trimmed}`);
}

function optionalUrlError(value: string, label: string, allowTemplate = false, baseUrl = ""): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (allowTemplate && isTemplateUrl(trimmed, baseUrl)) return null;
  return isHttpUrl(trimmed) ? null : `${label} must be a valid http(s) URL.`;
}

function validation(field: FieldKey, message: string): ValidationResult {
  return { field, message };
}

function validateState(state: ProviderFormState): ValidationResult | null {
  if (!state.name.trim()) return validation("name", "Provider name is required.");
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(state.name.trim()) || state.name.includes("..")) {
    return validation("name", "Provider name must be filesystem-safe.");
  }
  if (!state.displayName.trim()) return validation("displayName", "Display name is required.");
  for (const target of cleanList(state.apiTargets)) {
    if (!isApiTarget(target)) {
      return validation("apiTargets", "API targets must be http(s) URLs, bare hosts, or regex: patterns.");
    }
  }
  const docsError = optionalUrlError(state.docsUrl, "Docs URL");
  if (docsError) return validation("docsUrl", docsError);
  if (state.authType === "oauth2") {
    if (!state.oauth.authorizationUrl.trim()) {
      return validation("oauthAuthorizationUrl", "Authorization URL is required for OAuth providers.");
    }
    if (!state.oauth.tokenUrl.trim()) return validation("oauthTokenUrl", "Token URL is required for OAuth providers.");
    for (const [value, label, field] of [
      [state.oauth.baseUrl, "Base URL", "oauthBaseUrl"],
      [state.oauth.authorizationUrl, "Authorization URL", "oauthAuthorizationUrl"],
      [state.oauth.tokenUrl, "Token URL", "oauthTokenUrl"],
      [state.oauth.revocationUrl, "Revocation URL", "oauthRevocationUrl"],
      [state.oauth.deviceAuthorizationUrl, "Device authorization URL", "oauthDeviceAuthorizationUrl"],
    ] as const) {
      const error = optionalUrlError(value, label, label !== "Base URL", state.oauth.baseUrl);
      if (error) return validation(field, error);
    }
    if (state.flow === "device_code" && !state.oauth.deviceAuthorizationUrl.trim()) {
      return validation("oauthDeviceAuthorizationUrl", "Device authorization URL is required for device-code providers.");
    }
    const registrationError = optionalUrlError(state.registrationEndpoint, "Registration endpoint");
    if (registrationError) return validation("registrationEndpoint", registrationError);
  }
  if (state.authType === "browser") {
    const entryError = optionalUrlError(state.browser.entryUrl, "Browser entry URL");
    if (entryError) return validation("browserEntryUrl", entryError);
    const validateError = optionalUrlError(state.browser.validateUrl, "Browser validate URL");
    if (validateError) return validation("browserValidateUrl", validateError);
    if (Number.parseInt(state.browser.ttlHours, 10) <= 0) {
      return validation("browserTtlHours", "TTL hours must be greater than zero.");
    }
  }
  return null;
}

function fieldFromServerMessage(message: string): FieldKey | null {
  const normalized = message.toLowerCase();
  const entries: Array<[string, FieldKey]> = [
    ["docs_url", "docsUrl"],
    ["api_url", "apiTargets"],
    ["authorization_url", "oauthAuthorizationUrl"],
    ["token_url", "oauthTokenUrl"],
    ["revocation_url", "oauthRevocationUrl"],
    ["device_authorization_url", "oauthDeviceAuthorizationUrl"],
    ["base_url", "oauthBaseUrl"],
    ["registration.registration_endpoint", "registrationEndpoint"],
    ["registration_endpoint", "registrationEndpoint"],
    ["browser.entry_url", "browserEntryUrl"],
    ["browser.validate_url", "browserValidateUrl"],
    ["entry_url", "browserEntryUrl"],
    ["validate_url", "browserValidateUrl"],
  ];
  return entries.find(([needle]) => normalized.includes(needle))?.[1] || null;
}

function headerPrefixValue(apiKey: ProviderFormState["apiKey"]): string | null {
  if (apiKey.headerPrefixMode === "none") return null;
  if (apiKey.headerPrefixMode === "empty") return "";
  if (apiKey.headerPrefixMode === "custom") return apiKey.headerPrefixCustom.trim();
  return apiKey.headerPrefixMode;
}

function buildPayload(state: ProviderFormState): ProviderDefinitionPayload {
  const apiTargets = cleanList(state.apiTargets);
  const payload: ProviderDefinitionPayload = {
    schema_version: 1,
    name: state.name.trim(),
    display_name: state.displayName.trim(),
    auth_type: state.authType,
    flow: state.flow,
    type: state.providerType,
  };
  if (state.logo.trim()) payload.logo = state.logo.trim();
  if (state.description.trim()) payload.description = state.description.trim();
  if (state.docsUrl.trim()) payload.docs_url = state.docsUrl.trim();
  if (apiTargets.length === 1) payload.api_url = apiTargets[0];
  if (apiTargets.length > 1) payload.api_url = apiTargets;
  const exportRows = cleanRecord(state.exportRows);
  if (Object.keys(exportRows).length) payload.export = exportRows;

  if (state.authType === "oauth2") {
    payload.oauth = {
      authorization_url: state.oauth.authorizationUrl.trim(),
      token_url: state.oauth.tokenUrl.trim(),
      scopes: cleanList(state.oauth.scopes),
      authorization_params: cleanRecord(state.oauth.authorizationParams),
      pkce: state.oauth.pkce,
      supports_device_code: state.oauth.supportsDeviceCode,
      supports_dcr: state.oauth.supportsDcr,
      device_token_request: state.oauth.deviceTokenRequest,
      authorization_method: state.oauth.authorizationMethod,
    };
    if (state.oauth.baseUrl.trim()) payload.oauth.base_url = state.oauth.baseUrl.trim();
    if (state.oauth.revocationUrl.trim()) payload.oauth.revocation_url = state.oauth.revocationUrl.trim();
    if (state.oauth.deviceAuthorizationUrl.trim()) {
      payload.oauth.device_authorization_url = state.oauth.deviceAuthorizationUrl.trim();
    }
    if (state.registrationEndpoint.trim()) {
      payload.registration = { registration_endpoint: state.registrationEndpoint.trim() };
    }
  }

  if (state.authType === "api_key") {
    payload.api_key = {
      header_name: state.apiKey.headerName.trim() || "Authorization",
      header_prefix: headerPrefixValue(state.apiKey),
    };
    if (state.apiKey.keyPattern.trim()) payload.api_key.key_pattern = state.apiKey.keyPattern.trim();
    if (state.apiKey.keyPatternHint.trim()) payload.api_key.key_pattern_hint = state.apiKey.keyPatternHint.trim();
  }

  if (state.authType === "browser") {
    payload.browser = {
      entry_url: state.browser.entryUrl.trim(),
      domains: cleanList(state.browser.domains),
      auth_cookies: cleanList(state.browser.authCookies),
      ttl_hours: Number.parseInt(state.browser.ttlHours, 10) || 24,
      extra_headers: cleanRecord(state.browser.extraHeaders),
      extract: state.browser.extract
        .map((row) => ({
          cookie: row.cookie.trim(),
          header: row.header.trim(),
          prefix: row.prefix.trim(),
        }))
        .filter((row) => row.cookie && row.header),
    };
    if (state.browser.validateUrl.trim()) payload.browser.validate_url = state.browser.validateUrl.trim();
    if (state.browser.ttlFromCookie.trim()) payload.browser.ttl_from_cookie = state.browser.ttlFromCookie.trim();
  }

  return payload;
}

function Field({
  children,
  className,
  error,
  label,
}: {
  children: React.ReactNode;
  className?: string;
  error?: string;
  label: string;
}) {
  return (
    <label className={cn("grid gap-2 text-sm", className)}>
      <span className="text-muted-foreground">{label}</span>
      {children}
      {error ? <span className="text-xs text-destructive">{error}</span> : null}
    </label>
  );
}

function TextArea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      className={cn(
        "min-h-20 w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
        className,
      )}
      {...props}
    />
  );
}

function ListEditor({
  error,
  label,
  onChange,
  placeholder,
  values,
}: {
  error?: string;
  label: string;
  onChange: (values: string[]) => void;
  placeholder?: string;
  values: string[];
}) {
  return (
    <div className="grid gap-2">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="grid gap-2">
        {values.map((value, index) => (
          <div className="flex gap-2" key={index}>
            <Input
              aria-invalid={Boolean(error)}
              onChange={(event) => onChange(values.map((item, i) => (i === index ? event.target.value : item)))}
              placeholder={placeholder}
              value={value}
            />
            <Button
              aria-label={`Remove ${label}`}
              onClick={() => onChange(values.filter((_, i) => i !== index))}
              size="icon"
              type="button"
              variant="outline"
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </div>
      <Button onClick={() => onChange([...values, ""])} size="sm" type="button" variant="outline">
        <Plus />
        Add
      </Button>
      {error ? <span className="text-xs text-destructive">{error}</span> : null}
    </div>
  );
}

function KeyValueEditor({
  keyPlaceholder = "Key",
  label,
  onChange,
  rows,
  valuePlaceholder = "Value",
}: {
  keyPlaceholder?: string;
  label: string;
  onChange: (rows: KeyValueRow[]) => void;
  rows: KeyValueRow[];
  valuePlaceholder?: string;
}) {
  return (
    <div className="grid gap-2">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="grid gap-2">
        {rows.map((row) => (
          <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_2rem]" key={row.id}>
            <Input
              onChange={(event) =>
                onChange(rows.map((item) => (item.id === row.id ? { ...item, key: event.target.value } : item)))
              }
              placeholder={keyPlaceholder}
              value={row.key}
            />
            <Input
              onChange={(event) =>
                onChange(rows.map((item) => (item.id === row.id ? { ...item, value: event.target.value } : item)))
              }
              placeholder={valuePlaceholder}
              value={row.value}
            />
            <Button
              aria-label={`Remove ${label}`}
              onClick={() => onChange(rows.filter((item) => item.id !== row.id))}
              size="icon"
              type="button"
              variant="outline"
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </div>
      <Button onClick={() => onChange([...rows, { id: rowId(), key: "", value: "" }])} size="sm" type="button" variant="outline">
        <Plus />
        Add
      </Button>
    </div>
  );
}

function ExtractEditor({
  onChange,
  rows,
}: {
  onChange: (rows: ExtractRow[]) => void;
  rows: ExtractRow[];
}) {
  return (
    <div className="grid gap-2">
      <div className="text-sm text-muted-foreground">Cookie extraction</div>
      <div className="grid gap-2">
        {rows.map((row) => (
          <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.75fr)_2rem]" key={row.id}>
            <Input
              onChange={(event) =>
                onChange(rows.map((item) => (item.id === row.id ? { ...item, cookie: event.target.value } : item)))
              }
              placeholder="Cookie"
              value={row.cookie}
            />
            <Input
              onChange={(event) =>
                onChange(rows.map((item) => (item.id === row.id ? { ...item, header: event.target.value } : item)))
              }
              placeholder="Header"
              value={row.header}
            />
            <Input
              onChange={(event) =>
                onChange(rows.map((item) => (item.id === row.id ? { ...item, prefix: event.target.value } : item)))
              }
              placeholder="Prefix"
              value={row.prefix}
            />
            <Button
              aria-label="Remove cookie extraction"
              onClick={() => onChange(rows.filter((item) => item.id !== row.id))}
              size="icon"
              type="button"
              variant="outline"
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </div>
      <Button
        onClick={() => onChange([...rows, { id: rowId(), cookie: "", header: "", prefix: "" }])}
        size="sm"
        type="button"
        variant="outline"
      >
        <Plus />
        Add
      </Button>
    </div>
  );
}

function BooleanField({ checked, label, onChange }: { checked: boolean; label: string; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      <input checked={checked} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
      {label}
    </label>
  );
}

export function CustomProviderDialog({
  mode,
  onOpenChange,
  onSaved,
  open,
  provider,
}: {
  mode: "create" | "edit";
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  open: boolean;
  provider?: ProviderResponse | null;
}) {
  const [state, setState] = useState(() => initialState(provider));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const title = mode === "edit" ? "Edit custom provider" : "New custom provider";

  const flowOptions = FLOW_OPTIONS[state.authType];
  const payloadPreview = useMemo(() => buildPayload(state), [state]);

  function setAuthType(authType: AuthType) {
    setState((current) => ({ ...current, authType, flow: FLOW_OPTIONS[authType][0].value }));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFieldErrors({});
    const validationError = validateState(state);
    if (validationError) {
      setFieldErrors({ [validationError.field]: validationError.message });
      setMessage(validationError.message);
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      if (mode === "edit") {
        await updateCustomProvider(provider?.name || state.name, payloadPreview);
      } else {
        await createCustomProvider(payloadPreview);
      }
      onSaved();
      onOpenChange(false);
    } catch (error) {
      const errorMessage = error instanceof ApiError || error instanceof Error ? error.message : "Provider could not be saved.";
      const field = fieldFromServerMessage(errorMessage);
      if (field) {
        setFieldErrors({ [field]: errorMessage });
      }
      setMessage(errorMessage);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>Define how Authsome should authenticate and route this provider.</DialogDescription>
        </DialogHeader>
        <form className="grid gap-5" onSubmit={(event) => void save(event)}>
          <Card className="border-border/50 shadow-none">
            <CardHeader>
              <CardTitle>Basics</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <Field error={fieldErrors.name} label="Provider name">
                <Input
                  aria-invalid={Boolean(fieldErrors.name)}
                  disabled={mode === "edit"}
                  onChange={(event) => setState((current) => ({ ...current, name: event.target.value }))}
                  placeholder="custom-api"
                  required
                  value={state.name}
                />
              </Field>
              <Field error={fieldErrors.displayName} label="Display name">
                <Input
                  aria-invalid={Boolean(fieldErrors.displayName)}
                  onChange={(event) => setState((current) => ({ ...current, displayName: event.target.value }))}
                  placeholder="Custom API"
                  required
                  value={state.displayName}
                />
              </Field>
              <Field label="Type">
                <Select
                  onChange={(event) => setState((current) => ({ ...current, providerType: event.target.value as ProviderType }))}
                  value={state.providerType}
                >
                  {PROVIDER_TYPES.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Auth type">
                <Select onChange={(event) => setAuthType(event.target.value as AuthType)} value={state.authType}>
                  {AUTH_TYPES.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Flow">
                <Select
                  onChange={(event) => setState((current) => ({ ...current, flow: event.target.value as FlowType }))}
                  value={state.flow}
                >
                  {flowOptions.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Logo">
                <Input
                  onChange={(event) => setState((current) => ({ ...current, logo: event.target.value }))}
                  placeholder="img.logo.dev/name/example"
                  value={state.logo}
                />
              </Field>
              <Field className="md:col-span-2" label="Description">
                <TextArea
                  onChange={(event) => setState((current) => ({ ...current, description: event.target.value }))}
                  value={state.description}
                />
              </Field>
              <Field className="md:col-span-2" error={fieldErrors.docsUrl} label="Docs URL">
                <Input
                  aria-invalid={Boolean(fieldErrors.docsUrl)}
                  onChange={(event) => setState((current) => ({ ...current, docsUrl: event.target.value }))}
                  placeholder="https://docs.example.com/oauth"
                  value={state.docsUrl}
                />
              </Field>
              <div className="md:col-span-2">
                <ListEditor
                  error={fieldErrors.apiTargets}
                  label="API targets"
                  onChange={(apiTargets) => setState((current) => ({ ...current, apiTargets }))}
                  placeholder="https://api.example.com or regex:.*example\\.com$"
                  values={state.apiTargets}
                />
              </div>
            </CardContent>
          </Card>

          {state.authType === "oauth2" ? (
            <OAuthSection fieldErrors={fieldErrors} state={state} setState={setState} />
          ) : null}
          {state.authType === "api_key" ? (
            <ApiKeySection state={state} setState={setState} />
          ) : null}
          {state.authType === "browser" ? (
            <BrowserSection fieldErrors={fieldErrors} state={state} setState={setState} />
          ) : null}

          <Card className="border-border/50 shadow-none">
            <CardHeader>
              <CardTitle>Export</CardTitle>
            </CardHeader>
            <CardContent>
              <KeyValueEditor
                keyPlaceholder="Environment variable"
                label="Export mapping"
                onChange={(exportRows) => setState((current) => ({ ...current, exportRows }))}
                rows={state.exportRows}
                valuePlaceholder="Credential field"
              />
            </CardContent>
          </Card>

          {message ? <div className="text-sm text-destructive">{message}</div> : null}
          <DialogFooter>
            <Button onClick={() => onOpenChange(false)} type="button" variant="outline">
              Cancel
            </Button>
            <Button disabled={saving} type="submit">
              <Save />
              {saving ? "Saving" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function OAuthSection({
  fieldErrors,
  setState,
  state,
}: {
  fieldErrors: FieldErrors;
  setState: React.Dispatch<React.SetStateAction<ProviderFormState>>;
  state: ProviderFormState;
}) {
  return (
    <Card className="border-border/50 shadow-none">
      <CardHeader>
        <CardTitle>OAuth</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        <Field error={fieldErrors.oauthBaseUrl} label="Base URL">
          <Input
            aria-invalid={Boolean(fieldErrors.oauthBaseUrl)}
            onChange={(event) => setState((current) => ({ ...current, oauth: { ...current.oauth, baseUrl: event.target.value } }))}
            placeholder="https://github.com"
            value={state.oauth.baseUrl}
          />
        </Field>
        <Field label="Authorization method">
          <Select
            onChange={(event) =>
              setState((current) => ({
                ...current,
                oauth: { ...current.oauth, authorizationMethod: event.target.value as "body" | "basic" },
              }))
            }
            value={state.oauth.authorizationMethod}
          >
            <option value="body">Body</option>
            <option value="basic">Basic</option>
          </Select>
        </Field>
        <Field error={fieldErrors.oauthAuthorizationUrl} label="Authorization URL">
          <Input
            aria-invalid={Boolean(fieldErrors.oauthAuthorizationUrl)}
            onChange={(event) => setState((current) => ({ ...current, oauth: { ...current.oauth, authorizationUrl: event.target.value } }))}
            placeholder="{base_url}/oauth/authorize"
            required
            value={state.oauth.authorizationUrl}
          />
        </Field>
        <Field error={fieldErrors.oauthTokenUrl} label="Token URL">
          <Input
            aria-invalid={Boolean(fieldErrors.oauthTokenUrl)}
            onChange={(event) => setState((current) => ({ ...current, oauth: { ...current.oauth, tokenUrl: event.target.value } }))}
            placeholder="{base_url}/oauth/token"
            required
            value={state.oauth.tokenUrl}
          />
        </Field>
        <Field error={fieldErrors.oauthRevocationUrl} label="Revocation URL">
          <Input
            aria-invalid={Boolean(fieldErrors.oauthRevocationUrl)}
            onChange={(event) => setState((current) => ({ ...current, oauth: { ...current.oauth, revocationUrl: event.target.value } }))}
            value={state.oauth.revocationUrl}
          />
        </Field>
        <Field error={fieldErrors.oauthDeviceAuthorizationUrl} label="Device authorization URL">
          <Input
            aria-invalid={Boolean(fieldErrors.oauthDeviceAuthorizationUrl)}
            onChange={(event) =>
              setState((current) => ({ ...current, oauth: { ...current.oauth, deviceAuthorizationUrl: event.target.value } }))
            }
            value={state.oauth.deviceAuthorizationUrl}
          />
        </Field>
        <Field label="Device token request">
          <Select
            onChange={(event) =>
              setState((current) => ({
                ...current,
                oauth: { ...current.oauth, deviceTokenRequest: event.target.value as "oauth2_form" | "json" },
              }))
            }
            value={state.oauth.deviceTokenRequest}
          >
            <option value="oauth2_form">OAuth2 form</option>
            <option value="json">JSON</option>
          </Select>
        </Field>
        <Field error={fieldErrors.registrationEndpoint} label="DCR registration endpoint">
          <Input
            aria-invalid={Boolean(fieldErrors.registrationEndpoint)}
            onChange={(event) => setState((current) => ({ ...current, registrationEndpoint: event.target.value }))}
            value={state.registrationEndpoint}
          />
        </Field>
        <div className="grid gap-2 md:col-span-2">
          <div className="flex flex-wrap gap-4">
            <BooleanField
              checked={state.oauth.pkce}
              label="PKCE"
              onChange={(pkce) => setState((current) => ({ ...current, oauth: { ...current.oauth, pkce } }))}
            />
            <BooleanField
              checked={state.oauth.supportsDeviceCode}
              label="Supports device code"
              onChange={(supportsDeviceCode) =>
                setState((current) => ({ ...current, oauth: { ...current.oauth, supportsDeviceCode } }))
              }
            />
            <BooleanField
              checked={state.oauth.supportsDcr}
              label="Supports DCR"
              onChange={(supportsDcr) => setState((current) => ({ ...current, oauth: { ...current.oauth, supportsDcr } }))}
            />
          </div>
        </div>
        <div className="md:col-span-2">
          <ListEditor
            label="Scopes"
            onChange={(scopes) => setState((current) => ({ ...current, oauth: { ...current.oauth, scopes } }))}
            placeholder="repo"
            values={state.oauth.scopes}
          />
        </div>
        <div className="md:col-span-2">
          <KeyValueEditor
            label="Authorization params"
            onChange={(authorizationParams) =>
              setState((current) => ({ ...current, oauth: { ...current.oauth, authorizationParams } }))
            }
            rows={state.oauth.authorizationParams}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function ApiKeySection({
  setState,
  state,
}: {
  setState: React.Dispatch<React.SetStateAction<ProviderFormState>>;
  state: ProviderFormState;
}) {
  return (
    <Card className="border-border/50 shadow-none">
      <CardHeader>
        <CardTitle>API Key</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        <Field label="Header name">
          <Input
            onChange={(event) => setState((current) => ({ ...current, apiKey: { ...current.apiKey, headerName: event.target.value } }))}
            value={state.apiKey.headerName}
          />
        </Field>
        <Field label="Header prefix">
          <Select
            onChange={(event) =>
              setState((current) => ({
                ...current,
                apiKey: { ...current.apiKey, headerPrefixMode: event.target.value as ProviderFormState["apiKey"]["headerPrefixMode"] },
              }))
            }
            value={state.apiKey.headerPrefixMode}
          >
            <option value="Bearer">Bearer</option>
            <option value="Basic">Basic</option>
            <option value="Token">Token</option>
            <option value="empty">Empty string</option>
            <option value="none">None</option>
            <option value="custom">Custom</option>
          </Select>
        </Field>
        {state.apiKey.headerPrefixMode === "custom" ? (
          <Field label="Custom header prefix">
            <Input
              onChange={(event) =>
                setState((current) => ({ ...current, apiKey: { ...current.apiKey, headerPrefixCustom: event.target.value } }))
              }
              value={state.apiKey.headerPrefixCustom}
            />
          </Field>
        ) : null}
        <Field label="Key pattern">
          <Input
            onChange={(event) => setState((current) => ({ ...current, apiKey: { ...current.apiKey, keyPattern: event.target.value } }))}
            placeholder="^sk-[A-Za-z0-9_-]{20,}$"
            value={state.apiKey.keyPattern}
          />
        </Field>
        <Field className="md:col-span-2" label="Key pattern hint">
          <Input
            onChange={(event) =>
              setState((current) => ({ ...current, apiKey: { ...current.apiKey, keyPatternHint: event.target.value } }))
            }
            value={state.apiKey.keyPatternHint}
          />
        </Field>
      </CardContent>
    </Card>
  );
}

function BrowserSection({
  fieldErrors,
  setState,
  state,
}: {
  fieldErrors: FieldErrors;
  setState: React.Dispatch<React.SetStateAction<ProviderFormState>>;
  state: ProviderFormState;
}) {
  return (
    <Card className="border-border/50 shadow-none">
      <CardHeader>
        <CardTitle>Browser Session</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        <Field error={fieldErrors.browserEntryUrl} label="Entry URL">
          <Input
            aria-invalid={Boolean(fieldErrors.browserEntryUrl)}
            onChange={(event) => setState((current) => ({ ...current, browser: { ...current.browser, entryUrl: event.target.value } }))}
            placeholder="https://example.com/login"
            required
            value={state.browser.entryUrl}
          />
        </Field>
        <Field error={fieldErrors.browserValidateUrl} label="Validate URL">
          <Input
            aria-invalid={Boolean(fieldErrors.browserValidateUrl)}
            onChange={(event) => setState((current) => ({ ...current, browser: { ...current.browser, validateUrl: event.target.value } }))}
            value={state.browser.validateUrl}
          />
        </Field>
        <Field error={fieldErrors.browserTtlHours} label="TTL hours">
          <Input
            aria-invalid={Boolean(fieldErrors.browserTtlHours)}
            min={1}
            onChange={(event) => setState((current) => ({ ...current, browser: { ...current.browser, ttlHours: event.target.value } }))}
            type="number"
            value={state.browser.ttlHours}
          />
        </Field>
        <Field label="TTL from cookie">
          <Input
            onChange={(event) =>
              setState((current) => ({ ...current, browser: { ...current.browser, ttlFromCookie: event.target.value } }))
            }
            value={state.browser.ttlFromCookie}
          />
        </Field>
        <div className="md:col-span-2">
          <ListEditor
            label="Cookie domains"
            onChange={(domains) => setState((current) => ({ ...current, browser: { ...current.browser, domains } }))}
            placeholder=".example.com"
            values={state.browser.domains}
          />
        </div>
        <div className="md:col-span-2">
          <ListEditor
            label="Auth cookies"
            onChange={(authCookies) => setState((current) => ({ ...current, browser: { ...current.browser, authCookies } }))}
            placeholder="session"
            values={state.browser.authCookies}
          />
        </div>
        <div className="md:col-span-2">
          <KeyValueEditor
            label="Extra headers"
            onChange={(extraHeaders) => setState((current) => ({ ...current, browser: { ...current.browser, extraHeaders } }))}
            rows={state.browser.extraHeaders}
          />
        </div>
        <div className="md:col-span-2">
          <ExtractEditor
            onChange={(extract) => setState((current) => ({ ...current, browser: { ...current.browser, extract } }))}
            rows={state.browser.extract}
          />
        </div>
      </CardContent>
    </Card>
  );
}
