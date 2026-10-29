import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import LandingPage from "../features/landing/LandingPage";
import { api } from "../lib/api";
import { renderWithProviders } from "./utils";

vi.mock("../lib/api", () => ({ api: { authConfig: vi.fn(), register: vi.fn() } }));

beforeEach(() => {
  vi.mocked(api.authConfig).mockResolvedValue({ registration_enabled: true });
  vi.mocked(api.register).mockReset();
});

test("the landing page has a sign-up section while registration is open", async () => {
  renderWithProviders(<LandingPage />);
  expect(await screen.findByRole("heading", { level: 2, name: "Create an account" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sign up" })).toHaveAttribute("href", "#signup");
});

test("the section still shows when the registration check cannot connect", async () => {
  vi.mocked(api.authConfig).mockRejectedValue(new Error("offline"));
  renderWithProviders(<LandingPage />);
  expect(await screen.findByRole("heading", { level: 2, name: "Create an account" })).toBeInTheDocument();
});

test("the section is hidden when the server says registration is closed", async () => {
  vi.mocked(api.authConfig).mockResolvedValue({ registration_enabled: false });
  renderWithProviders(<LandingPage />);
  expect(await screen.findByText(/created by an administrator/)).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Create an account" })).not.toBeInTheDocument();
});

test("it validates, then posts the details and offers sign-in", async () => {
  vi.mocked(api.register).mockResolvedValue({ id: "u1", email: "a@b.co", full_name: "Ada", role: "analyst" } as never);
  renderWithProviders(<LandingPage />);
  const form = await screen.findByRole("form", { name: "Create an account" });
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("Email is required")).toBeInTheDocument();
  expect(api.register).not.toHaveBeenCalled();

  await userEvent.type(screen.getByLabelText(/^Full name/), "Ada");
  await userEvent.type(screen.getByLabelText(/^Email/), "a@b.co");
  await userEvent.type(screen.getByLabelText(/^Password/), "a-long-password");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("Account created. You can sign in now.")).toBeInTheDocument();
  expect(api.register).toHaveBeenCalledWith("a@b.co", "a-long-password", "Ada");
  expect(form).not.toBeInTheDocument();
});

test("a server refusal is shown in the form", async () => {
  vi.mocked(api.register).mockRejectedValue(new Error("Registration is closed."));
  renderWithProviders(<LandingPage />);
  await userEvent.type(await screen.findByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText(/^Password/), "a-long-password");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Registration is closed.");
});
