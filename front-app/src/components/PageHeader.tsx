interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: PageHeaderProps): JSX.Element {
  return (
    <header className="flex shrink-0 items-end justify-between gap-4 border-b border-border bg-background/40 px-6 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/30">
      <div>
        <h1 className="text-base font-semibold tracking-tight">{title}</h1>
        {subtitle && (
          <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}
