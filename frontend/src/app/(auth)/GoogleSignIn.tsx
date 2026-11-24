import { googleLoginUrl } from "@/lib/urls";
import { ButtonLink } from "@/components/ui/Button";
import GoogleIcon from "@/components/ui/GoogleIcon";

/** "Continue with Google" plus the "or" divider before the email form. */
export default function GoogleSignIn({ nextPath }: { nextPath: string }) {
  return (
    <>
      {/* native: an API route, so a full navigation, not client routing. */}
      <ButtonLink href={googleLoginUrl(nextPath)} native variant="outlined" size="lg" block icon={<GoogleIcon />} className="mb-6">
        Continue with Google
      </ButtonLink>
      <div className="flex items-center gap-3 mb-6" aria-hidden="true">
        <span className="h-px flex-1 bg-outline-variant" />
        <span className="text-label-medium text-on-surface-variant">or</span>
        <span className="h-px flex-1 bg-outline-variant" />
      </div>
    </>
  );
}
