import {
  Clock,
  Palmtree,
  Gauge,
  CalendarCog,
  TrendingUp,
  House,
  type LucideIcon,
} from "lucide-react";

/**
 * The six policies actually in the index.
 *
 * Titles and summaries are taken from each document's own
 * "Purpose and Scope" section, not invented, so the Policies
 * page describes the corpus the answers come from.
 */
export interface Policy {
  id: string;
  title: string;
  summary: string;
  icon: LucideIcon;
}

export const POLICIES: Policy[] = [
  {
    id: "HR-201",
    title: "Working Hours & Attendance",
    summary:
      "The standard working week, how attendance is recorded, overtime, breaks, and reporting absence.",
    icon: Clock,
  },
  {
    id: "HR-202",
    title: "Annual Leave",
    summary:
      "How much leave employees receive, how it accrues, carry-over, and the process for requesting it.",
    icon: Palmtree,
  },
  {
    id: "HR-203",
    title: "Performance Management",
    summary:
      "Objective setting, ongoing feedback, formal reviews, and how performance ratings are applied.",
    icon: Gauge,
  },
  {
    id: "HR-204",
    title: "Flexible Working",
    summary:
      "What flexible working means, who may apply, eligibility, and how to make a request.",
    icon: CalendarCog,
  },
  {
    id: "HR-205",
    title: "Promotion & Progression",
    summary:
      "How employees progress to a higher level, eligibility requirements, and the nomination process.",
    icon: TrendingUp,
  },
  {
    id: "HR-207",
    title: "Remote & Hybrid Working",
    summary:
      "Working from home, hybrid arrangements, equipment and expenses, and working abroad.",
    icon: House,
  },
];

/**
 * Quick prompts.
 *
 * Each one is a question this corpus genuinely answers - they
 * retrieve at roughly 0.8 rather than the 0.57 a vague query
 * like "hey" scores. A chip that leads to a refusal teaches
 * the user the tool is broken when it is working correctly.
 */
export interface QuickPrompt {
  label: string;
  question: string;
  icon: LucideIcon;
}

export const QUICK_PROMPTS: QuickPrompt[] = [
  {
    label: "Annual leave",
    question: "How many days of annual leave do I get?",
    icon: Palmtree,
  },
  {
    label: "Working hours",
    question: "What are my standard working hours?",
    icon: Clock,
  },
  {
    label: "Remote work",
    question: "How many days a week can I work from home?",
    icon: House,
  },
  {
    label: "Flexible working",
    question:
      "How long must I work here before I can request flexible working?",
    icon: CalendarCog,
  },
  {
    label: "Performance reviews",
    question: "How am I rated in my performance review?",
    icon: Gauge,
  },
];

export function policyById(id: string): Policy | undefined {
  return POLICIES.find((policy) => policy.id === id);
}
