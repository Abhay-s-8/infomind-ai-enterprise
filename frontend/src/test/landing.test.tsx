import { screen } from "@testing-library/react";
import { Outlet, useLocation } from "react-router-dom";
import { vi } from "vitest";
import App from "../App";
import LandingPage from "../features/landing/LandingPage";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { renderWithProviders } from "./utils";

vi.mock("../lib/api", () => ({ api: { authConfig: vi.fn() } }));
vi.mock("../lib/auth", () => ({ useAuth: vi.fn() }));
// The signed-in pages are covered elsewhere; here only the routing around them matters.
vi.mock("../components/Layout", () => ({ default: () => <Outlet /> }));
vi.mock("../features/dashboard/DashboardPage", () => ({ default: () => <h1>Dashboard page</h1> }));
vi.mock("../features/reviews/ReviewsPage", () => ({ default: () => <h1>Reviews page</h1> }));
vi.mock("../features/auth/LoginPage", () => ({
  default: ({ initialMode = "login" }: { initialMode?: string }) => <h1>Auth page: {initialMode} at {useLocation().pathname}</h1>,
}));

const auth = (user: { role: string } | null, loading = false) =>
  vi.mocked(useAuth).mockReturnValue({ user, loading, can: (...r: string[]) => !!user && (user.role === "admin" || r.includes(user.role)) } as never);

beforeEach(() => {
  auth(null);
  vi.mocked(api.authConfig).mockResolvedValue({ registration_enabled: true });
});

test("visitors see the public website at the root, not the sign-in form", async () => {
  renderWithProviders(<App />, "/");
  expect(await screen.findByRole("heading", { level: 1, name: /Find answers in your documents/ })).toBeInTheDocument();
  expect(screen.queryByText(/Auth page/)).not.toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /Sign in/ })[0]).toHaveAttribute("href", "/login");
});

test("Create account is offered only while the server accepts registrations", async () => {
  const { unmount } = renderWithProviders(<LandingPage />);
  expect((await screen.findAllByRole("link", { name: "Create account" }))[0]).toHaveAttribute("href", "/register");
  unmount();
  vi.mocked(api.authConfig).mockResolvedValue({ registration_enabled: false });
  renderWithProviders(<LandingPage />);
  expect(await screen.findByText(/created by an administrator/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Create account" })).not.toBeInTheDocument();
});

test("when the registration check fails the page still works and promises nothing", async () => {
  vi.mocked(api.authConfig).mockRejectedValue(new Error("offline"));
  renderWithProviders(<LandingPage />);
  expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Create account" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /Sign in/ }).length).toBeGreaterThan(0);
});

test("sign-in and register are separate pages; protected pages send visitors to sign in", async () => {
  const { unmount } = renderWithProviders(<App />, "/register");
  expect(await screen.findByText(/Auth page: register at \/register/)).toBeInTheDocument();
  unmount();
  renderWithProviders(<App />, "/documents");
  expect(await screen.findByText(/Auth page: login at \/login/)).toBeInTheDocument();
});

test("signed-in users skip the website: analysts land on the overview, reviewers on the review queue", async () => {
  auth({ role: "analyst" });
  const { unmount } = renderWithProviders(<App />, "/");
  expect(await screen.findByText("Dashboard page")).toBeInTheDocument();
  unmount();
  auth({ role: "reviewer" });
  renderWithProviders(<App />, "/");
  expect(await screen.findByText("Reviews page")).toBeInTheDocument();
});

test("while a saved session is being restored the root shows a spinner, not the website", () => {
  auth(null, true);
  renderWithProviders(<App />, "/");
  expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  expect(screen.getByText(/Restoring session/)).toBeInTheDocument();
});
