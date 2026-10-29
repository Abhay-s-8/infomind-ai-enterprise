import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import type { z } from "zod";
import { Button, Field, Input } from "../../components/ui";
import { api } from "../../lib/api";
import { registerSchema } from "../../lib/utils";

type FormValues = z.infer<typeof registerSchema>;

/** Sign-up on the public page, posting to the same register call as /register. */
export default function SignupSection() {
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState(false);
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormValues>({ resolver: zodResolver(registerSchema) });

  const onSubmit = async (v: FormValues) => {
    setError(null);
    try {
      await api.register(v.email, v.password, v.full_name ?? "");
      setCreated(true);
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  };

  return (
    <section id="signup" className="mx-auto grid w-full max-w-7xl scroll-mt-20 gap-10 px-4 py-16 md:grid-cols-12 md:px-8 md:py-24">
      <div className="md:col-span-5">
        <h2 className="text-3xl md:text-4xl">Create an account</h2>
        <p className="mt-3 max-w-md text-base text-muted">New accounts are analyst accounts. The password needs at least 10 characters.</p>
      </div>
      <div className="md:col-span-7">
        <div className="rounded-lg border border-border bg-surface p-6">
          {created ? (
            <div role="status" className="space-y-4">
              <p className="text-base text-ok">Account created. You can sign in now.</p>
              <Link to="/login" className="inline-flex min-h-10 items-center rounded-md border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors duration-micro ease-out hover:bg-accent/90 active:bg-accent/80">Sign in</Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4" aria-label="Create an account">
              <Field label="Full name" error={errors.full_name?.message}><Input autoComplete="name" {...register("full_name")} /></Field>
              <Field label="Email" error={errors.email?.message}><Input type="email" autoComplete="email" {...register("email")} /></Field>
              <Field label="Password" error={errors.password?.message}><Input type="password" autoComplete="new-password" {...register("password")} /></Field>
              {error && <p role="alert" className="text-sm text-danger">{error}</p>}
              <Button type="submit" loading={isSubmitting} className="w-full">Create account</Button>
            </form>
          )}
        </div>
      </div>
    </section>
  );
}
