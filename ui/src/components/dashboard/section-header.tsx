export function SectionHeader({ description, title }: { description: string; title: string }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold leading-tight text-foreground">{title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
