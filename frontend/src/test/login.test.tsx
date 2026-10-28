import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import LoginPage from "../features/auth/LoginPage";
import { api } from "../lib/api";
import { renderWithProviders } from "./utils";

const login = vi.fn();
vi.mock("../lib/auth", () => ({ useAuth: () => ({ login }) }));
vi.mock("../lib/api", () => ({ api: { register: vi.fn(), authConfig: vi.fn() } }));

beforeEach(() => { // braces: a returned mock would be run as a teardown
  login.mockReset();
  vi.mocked(api.authConfig).mockResolvedValue({ registration_enabled: true });
});

test("shows validation errors and does not call the API for empty input", async () => {
  renderWithProviders(<LoginPage />);
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText("Email is required")).toBeInTheDocument();
  expect(screen.getByText("Password is required")).toBeInTheDocument();
  expect(login).not.toHaveBeenCalled();
});

test("submits valid credentials", async () => {
  login.mockResolvedValue(undefined);
  renderWithProviders(<LoginPage />);
  await userEvent.type(screen.getByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "pw-123456789");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(login).toHaveBeenCalledWith("a@b.co", "pw-123456789"));
});

test("displays the server error on failed login", async () => {
  login.mockRejectedValue(new Error("Invalid email or password."));
  renderWithProviders(<LoginPage />);
  await userEvent.type(screen.getByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
});

test("registration requires a 10+ character password", async () => {
  renderWithProviders(<LoginPage />);
  await userEvent.click(await screen.findByRole("button", { name: /Need an account/ }));
  await userEvent.type(screen.getByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "short");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("Use at least 10 characters")).toBeInTheDocument();
});

test("a server that has registration switched off shows no sign-up form, only a note", async () => {
  vi.mocked(api.authConfig).mockResolvedValue({ registration_enabled: false });
  renderWithProviders(<LoginPage initialMode="register" />, "/register");
  expect(await screen.findByText(/Registration is closed on this site/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument(); // falls back to the sign-in form
  expect(screen.queryByRole("button", { name: /Need an account/ })).not.toBeInTheDocument();
});

test("the register page opens the sign-up form when registration is on, and links back home", async () => {
  renderWithProviders(<LoginPage initialMode="register" />, "/register");
  expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Back to home/ })).toHaveAttribute("href", "/");
});
