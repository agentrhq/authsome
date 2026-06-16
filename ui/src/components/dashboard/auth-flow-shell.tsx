"use client";

import { motion } from "framer-motion";
import { KeyRound, Shield, Cpu, Lock } from "lucide-react";
import Image from "next/image";
import { ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const FEATURES = [
  {
    icon: KeyRound,
    title: "One CLI, every provider",
    description: "GitHub, Google, Okta, Linear, OpenAI — connect any OAuth or API-key provider in seconds.",
  },
  {
    icon: Shield,
    title: "Encrypted at rest",
    description: "Credentials are AES-encrypted in the vault. Secrets are protected at rest and in transit.",
  },
  {
    icon: Cpu,
    title: "Built for agents",
    description: "Give AI agents scoped, revocable access to your accounts — without sharing raw tokens.",
  },
  {
    icon: Lock,
    title: "Proof-of-Possession auth",
    description: "Every request is signed with Ed25519. No bearer tokens floating around.",
  },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.1, delayChildren: 0.2 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

export function AuthFlowShell({
  children,
  description,
  size = "compact",
  title,
}: {
  children?: ReactNode;
  description: string;
  size?: "compact" | "wide";
  title: string;
}) {
  if (size === "wide") {
    return (
      <main className="flex min-h-screen items-center bg-background px-4 py-8 sm:px-6 lg:px-10">
        <section className="mx-auto grid w-full max-w-6xl gap-12 lg:grid-cols-[1fr_1fr] lg:items-center">
          <motion.div
            className="max-w-lg"
            initial="hidden"
            animate="visible"
            variants={containerVariants}
          >
            <motion.div variants={itemVariants}>
              <Image
                alt="Authsome"
                className="mb-8 size-12 rounded-lg"
                height={48}
                src="/logo.svg"
                width={48}
              />
            </motion.div>

            <motion.h1
              className="text-3xl font-extrabold tracking-tight lg:text-4xl"
              variants={itemVariants}
            >
              {title}
            </motion.h1>

            <motion.p
              className="mt-3 text-base leading-7 text-muted-foreground"
              variants={itemVariants}
            >
              {description}
            </motion.p>

            <motion.div
              className="mt-10 grid gap-5"
              variants={containerVariants}
              initial="hidden"
              animate="visible"
            >
              {FEATURES.map((feature) => (
                <motion.div
                  key={feature.title}
                  className="flex gap-4"
                  variants={itemVariants}
                >
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/5 text-primary">
                    <feature.icon className="size-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold">{feature.title}</p>
                    <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">
                      {feature.description}
                    </p>
                  </div>
                </motion.div>
              ))}
            </motion.div>

          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.3, ease: "easeOut" }}
          >
            {children}
          </motion.div>
        </section>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center bg-background px-4 py-8 sm:px-6 lg:px-10">
      <motion.section
        className="mx-auto w-full max-w-md"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      >
        <Card className="border-border/70 shadow-none">
          <CardHeader>
            <Image alt="Authsome" className="mb-3 size-9 rounded-lg" height={36} src="/logo.svg" width={36} />
            <CardTitle className="text-base">{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          {children ? <CardContent>{children}</CardContent> : null}
        </Card>
      </motion.section>
    </main>
  );
}
