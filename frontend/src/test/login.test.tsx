import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import LoginPage from "../features/auth/LoginPage";
import { renderWithProviders } from "./utils";

const login = vi.fn();
vi.mock("../lib/auth", () => ({ useAuth: () => ({ login }) }));
vi.mock("../lib/api", () => ({ api: { register: vi.fn() } }));

beforeEach(() => { login.mockReset(); }); // braces: a returned mock would be run as a teardown

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
  await userEvent.click(screen.getByRole("button", { name: /Need an account/ }));
  await userEvent.type(screen.getByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "short");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("Use at least 10 characters")).toBeInTheDocument();
});
