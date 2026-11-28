import { ButtonLink } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-surface text-on-surface px-4">
      <main id="main" className="w-full max-w-md rounded-xl border border-outline-variant bg-surface-container-low p-8 text-center">
        <p className="font-mono text-label-medium text-on-surface-variant tabular-nums">404</p>
        <h1 className="mt-2 text-headline-small font-semibold text-on-surface">Page not found</h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          The page you&apos;re looking for doesn&apos;t exist or may have moved.
        </p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <ButtonLink href="/jobs" variant="filled">
            Open job board
          </ButtonLink>
          <ButtonLink href="/" variant="outlined">
            Home
          </ButtonLink>
        </div>
      </main>
    </div>
  );
}
