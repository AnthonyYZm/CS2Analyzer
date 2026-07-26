import { create } from "zustand";
import type { Locale } from "./types";

interface UiState {
  locale: Locale;
  selectedMatches: string[];
  setLocale: (locale: Locale) => void;
  toggleMatch: (id: string) => void;
  clearMatches: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  locale: "zh-CN",
  selectedMatches: [],
  setLocale: (locale) => set({ locale }),
  toggleMatch: (id) =>
    set((state) => ({
      selectedMatches: state.selectedMatches.includes(id)
        ? state.selectedMatches.filter((item) => item !== id)
        : [...state.selectedMatches, id],
    })),
  clearMatches: () => set({ selectedMatches: [] }),
}));
