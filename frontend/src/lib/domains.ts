import type { Incident } from "../types";

export interface DomainDefinition {
  key: string;
  label: string;
  description: string;
  path: string;
  configured: boolean;
  services: string[];
}

export const domainDefinitions: DomainDefinition[] = [
  {
    key: "it",
    label: "IT Operations",
    description: "Incidents, deployments, configuration, and service health.",
    path: "/incidents",
    configured: true,
    services: ["checkout", "payment", "user", "database", "inventory"]
  },
  {
    key: "revenue",
    label: "Revenue",
    description: "Payment and checkout signals from the ShopFlow environment.",
    path: "/business-health",
    configured: true,
    services: ["payment", "checkout"]
  },
  {
    key: "support",
    label: "Customer Support",
    description: "Customer issue and escalation sources.",
    path: "/operations",
    configured: true,
    services: ["support"]
  },
  {
    key: "supply-chain",
    label: "Supply Chain",
    description: "Inventory, suppliers, shipments, and order signals.",
    path: "/operations",
    configured: true,
    services: ["inventory"]
  },
  {
    key: "contracts",
    label: "Contracts",
    description: "Obligations, renewals, and penalty evidence.",
    path: "/operations",
    configured: false,
    services: []
  },
  {
    key: "cloud",
    label: "Cloud Infrastructure",
    description: "Resource, usage, and cost anomaly signals.",
    path: "/operations",
    configured: false,
    services: []
  },
  {
    key: "data",
    label: "Data Quality",
    description: "Pipeline, freshness, and data quality signals.",
    path: "/operations",
    configured: false,
    services: []
  },
  {
    key: "compliance",
    label: "Compliance",
    description: "Controls, evidence, and compliance gaps.",
    path: "/operations",
    configured: false,
    services: []
  }
];

export function incidentsForDomain(incidents: Incident[], domain: DomainDefinition): Incident[] {
  return incidents.filter((incident) => {
    const service = incident.service.toLowerCase();
    return domain.services.some((knownService) => service.includes(knownService));
  });
}
