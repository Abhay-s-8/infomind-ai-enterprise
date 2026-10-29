import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import type { z } from "zod";
import { Button, Field, Input } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { loginSchema, registerSchema } from "../../lib/utils";

type FormValues = z.infer<typeof registerSchema>;

type Mode = "login" | "register";

export default function LoginPage({ initialMode = "login" }: { initialMode?: Mode }) {
  const { login } = useAuth();
  const config = useQuery({ queryKey: ["auth-config"], queryFn: api.authConfig, retry: 1, staleTime: 60_000 });
  const registrationOpen = config.data?.registration_enabled === true;
  const registrationClosed = config.data?.registration_enabled === false;
  const [wanted, setWanted] = useState<Mode>(initialMode);
  const mode: Mode = registrationClosed ? "login" : wanted; // a closed server never shows the sign-up form
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: (values, ctx, opts) => zodResolver(mode === "login" ? loginSchema : registerSchema)(values, ctx, opts) as never,
  });

  const onSubmit = async (v: FormValues) => {
    setError(null);
    setNotice(null);
    try {
      if (mode === "register") {
        await api.register(v.email, v.password, v.full_name ?? "");
        setNotice("Account created. You can sign in now.");
        setWanted("login");
      } else {
        await login(v.email, v.password);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  };

  return (
    <div className="flex min-h-full flex-col">
      <div className="mx-auto w-full max-w-7xl px-4 py-4 md:px-8">
        <Link to="/" className="link text-sm text-muted">← Back to home</Link>
      </div>
      <div className="flex flex-1 items-center justify-center px-4 pb-16">
        <div className="w-full max-w-sm">
          <h1 className="text-3xl">InfoMind AI Enterprise</h1>
          <p className="mb-8 mt-2 text-base text-muted">{mode === "login" ? "Sign in to your workspace" : "Create an analyst account"}</p>
          <div className="rounded-lg border border-border bg-surface p-6">
            <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
              {mode === "register" && (
                <Field label="Full name" error={errors.full_name?.message}><Input {...register("full_name")} autoComplete="name" /></Field>
              )}
              <Field label="Email" error={errors.email?.message}><Input type="email" autoComplete="email" {...register("email")} /></Field>
              <Field label="Password" error={errors.password?.message}>
                <Input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} {...register("password")} />
              </Field>
              {error && <p role="alert" className="text-sm text-danger">{error}</p>}
              {notice && <p role="status" className="text-sm text-ok">{notice}</p>}
              <Button type="submit" loading={isSubmitting} className="w-full">{mode === "login" ? "Sign in" : "Create account"}</Button>
            </form>
            {(registrationOpen || mode === "register") && (
              <button className="link mt-2 inline-flex min-h-10 items-center text-sm" onClick={() => { setWanted(mode === "login" ? "register" : "login"); setError(null); }}>
                {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
              </button>
            )}
            {registrationClosed && (
              <p className="mt-4 text-sm text-muted">{initialMode === "register" ? "Registration is closed on this site. " : ""}New accounts are created by an administrator.</p>
            )}
          </div>
          <p className="mt-6 text-sm text-muted">Educational prototype. Use synthetic or public data only.</p>
        </div>
      </div>
    </div>
  );
}
