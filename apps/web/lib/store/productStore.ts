/**
 * lib/store/productStore.ts
 */

import { create } from 'zustand';

export interface Product {
  id: string;
  name: string;
  slug: string;
  category: string;
  description: string;
  website: string;
  status: string;
  organizationId: string;
}

export interface ProductBrain {
  productId: string;
  icp: string;
  personas: string[];
  industries: string[];
  problemsSolved: string[];
  problemsNotSolved: string[];
  keywords: string[];
  negativeKeywords: string[];
  competitors: string[];
}

interface ProductStore {
  products: Map<string, Product>;
  brains: Map<string, ProductBrain>;
  setProducts: (products: Product[]) => void;
  upsertProduct: (product: Product) => void;
  setBrain: (brain: ProductBrain) => void;
  getProduct: (id: string) => Product | undefined;
}

export const useProductStore = create<ProductStore>((set, get) => ({
  products: new Map(),
  brains: new Map(),

  setProducts: (products) => {
    const map = new Map<string, Product>();
    for (const p of products) map.set(p.id, p);
    set({ products: map });
  },

  upsertProduct: (product) =>
    set((state) => {
      const map = new Map(state.products);
      map.set(product.id, product);
      return { products: map };
    }),

  setBrain: (brain) =>
    set((state) => {
      const map = new Map(state.brains);
      map.set(brain.productId, brain);
      return { brains: map };
    }),

  getProduct: (id) => get().products.get(id),
}));
