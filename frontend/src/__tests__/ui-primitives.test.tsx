import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import Alert from "@/components/ui/Alert";
import { Button, ButtonLink } from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { Input, Select } from "@/components/ui/Input";
import Skeleton, { SkeletonGroup } from "@/components/ui/Skeleton";

describe("Button", () => {
  it("defaults to type=button so it never submits a form by accident", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("type", "button");
  });

  it("is disabled and busy while loading, and ignores clicks", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Saving…
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Saving…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    await userEvent.setup().click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("is not marked busy when idle", () => {
    render(<Button>Go</Button>);
    expect(screen.getByRole("button")).not.toHaveAttribute("aria-busy");
  });

  it("exposes toggle state through aria-pressed", () => {
    render(
      <Button variant="secondary" aria-pressed={true}>
        Remote
      </Button>,
    );
    expect(screen.getByRole("button", { name: "Remote" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("ButtonLink", () => {
  it("opens external links in a new tab without an opener", () => {
    render(
      <ButtonLink href="https://example.com/apply" external>
        Apply
      </ButtonLink>,
    );
    const link = screen.getByRole("link", { name: "Apply" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("keeps native links in the same tab", () => {
    render(
      <ButtonLink href="/api/v1/auth/google/login" native>
        Continue with Google
      </ButtonLink>,
    );
    const link = screen.getByRole("link", { name: "Continue with Google" });
    expect(link).toHaveAttribute("href", "/api/v1/auth/google/login");
    expect(link).not.toHaveAttribute("target");
  });
});

describe("Field", () => {
  it("labels its control", () => {
    render(
      <Field label="Email">
        <Input type="email" />
      </Field>,
    );
    expect(screen.getByLabelText("Email")).toHaveAttribute("type", "email");
  });

  it("describes the control with its hint and marks errors invalid", () => {
    render(
      <Field label="Password" hint="At least 8 characters." error="Too short.">
        <Input type="password" />
      </Field>,
    );
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAccessibleDescription("At least 8 characters. Too short.");
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("leaves a valid control unmarked", () => {
    render(
      <Field label="Name">
        <Input />
      </Field>,
    );
    const input = screen.getByLabelText("Name");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).not.toHaveAttribute("aria-describedby");
  });

  it("keeps a visually hidden label accessible", () => {
    render(
      <Field label="Article URL" labelVisible={false}>
        <Input type="url" />
      </Field>,
    );
    expect(screen.getByLabelText("Article URL")).toBeInTheDocument();
    expect(screen.getByText("Article URL")).toHaveClass("sr-only");
  });

  it("wires a Select the same way", () => {
    render(
      <Field label="Category">
        <Select>
          <option value="">All</option>
        </Select>
      </Field>,
    );
    expect(screen.getByLabelText("Category").tagName).toBe("SELECT");
  });

  it("gives each field its own id", () => {
    render(
      <>
        <Field label="First">
          <Input />
        </Field>
        <Field label="Second">
          <Input />
        </Field>
      </>,
    );
    expect(screen.getByLabelText("First").id).not.toBe(screen.getByLabelText("Second").id);
  });
});

describe("Input outside a Field", () => {
  it("accepts its own accessible name", () => {
    render(<Input aria-label="Search role or company" leadingIcon={<svg />} />);
    expect(screen.getByRole("textbox", { name: "Search role or company" })).toBeInTheDocument();
  });
});

describe("Alert", () => {
  it("announces errors assertively", () => {
    render(<Alert variant="error">Invalid credentials.</Alert>);
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid credentials.");
  });

  it("announces info politely", () => {
    render(<Alert>Fetching headlines…</Alert>);
    expect(screen.getByRole("status")).toHaveTextContent("Fetching headlines…");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("Skeleton", () => {
  it("hides blocks from assistive tech and announces one label", () => {
    const { container } = render(
      <SkeletonGroup label="Loading articles">
        <Skeleton />
        <Skeleton />
      </SkeletonGroup>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading articles");
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(2);
  });
});
