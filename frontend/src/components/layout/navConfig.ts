import {
  Bell,
  Boxes,
  FileBarChart,
  LayoutDashboard,
  MapPin,
  PackageSearch,
  ScrollText,
  Satellite,
  Settings,
  ShieldCheck,
  Truck,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  permission?: string;
  requiresRole?: string;
}

export const navItems: NavItem[] = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard, permission: "dashboard.view" },
  { label: "Assets", to: "/assets", icon: Boxes, permission: "assets.view" },
  { label: "Inventory", to: "/inventory", icon: PackageSearch, permission: "inventory.view" },
  { label: "Suppliers & Procurement", to: "/procurement", icon: Truck, permission: "suppliers.view" },
  { label: "Starlink Management", to: "/starlink", icon: Satellite, permission: "starlink.view" },
  { label: "Notifications", to: "/notifications", icon: Bell, permission: "notifications.view" },
  { label: "Reports", to: "/reports", icon: FileBarChart, permission: "reports.view" },
  { label: "Users", to: "/users", icon: Users, permission: "users.view" },
  { label: "Roles & Permissions", to: "/roles", icon: ShieldCheck, permission: "roles.view" },
  { label: "Locations & Warehouses", to: "/locations", icon: MapPin, permission: "locations.view" },
  { label: "Audit Log", to: "/audit", icon: ScrollText, permission: "audit.view" },
  { label: "Settings", to: "/settings", icon: Settings },
];
