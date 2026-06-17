import { H4 } from "@/components/ui/typography";
import { Muted } from "@/components/ui/typography";

export function SectionHeader({ description, title }: { description: string; title: string }) {
  return (
    <div>
      <H4 className="leading-tight">{title}</H4>
      <Muted className="mt-1">{description}</Muted>
    </div>
  );
}
