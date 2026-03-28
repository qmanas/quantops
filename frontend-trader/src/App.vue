<template>
  <div class="h-full w-full flex flex-col bg-background text-zinc-100 font-sans">
    <!-- Header -->
    <header class="h-16 border-b border-zinc-800 flex items-center justify-between px-6 bg-surface/50 backdrop-blur-md sticky top-0 z-50">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center border border-primary/30">
          <BarChart3 class="w-5 h-5 text-primary" />
        </div>
        <h1 class="text-xl font-bold tracking-tight">Trader Command <span class="text-zinc-500 font-normal text-sm ml-2">v1.2</span></h1>
      </div>
      
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900 border border-zinc-800">
          <div class="w-2 h-2 rounded-full bg-success animate-pulse"></div>
          <span class="text-xs font-medium text-zinc-400 uppercase tracking-widest">System Active</span>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 flex overflow-hidden">
      <!-- Sidebar -->
      <aside class="w-80 border-r border-zinc-800 flex flex-col bg-surface/20">
        <div class="p-4 border-b border-zinc-800/50">
          <h2 class="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Strategy Windows</h2>
          <div class="space-y-2">
            <div v-for="mission in missions" :key="mission.id" 
                 class="group p-3 rounded-xl border border-zinc-800/50 hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer"
                 :class="{'border-primary bg-primary/10': selectedMission?.id === mission.id}">
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm font-bold truncate">{{ mission.name }}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 uppercase">{{ mission.status }}</span>
              </div>
              <div class="text-[11px] text-zinc-500 flex items-center gap-1">
                <Calendar class="w-3 h-3" />
                {{ formatDate(mission.start_ts) }}
              </div>
            </div>
            
            <button class="w-full py-2.5 rounded-xl border border-dashed border-zinc-700 text-zinc-500 text-xs font-medium hover:text-zinc-300 hover:border-zinc-500 transition-colors flex items-center justify-center gap-2">
              <Plus class="w-4 h-4" />
              New Strategy Window
            </button>
          </div>
        </div>
        
        <div class="flex-1 p-4 overflow-y-auto">
          <h2 class="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Selected Window</h2>
          <div v-if="selection" class="space-y-4">
            <div class="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
              <div class="text-[11px] text-zinc-500 uppercase tracking-wide mb-1">Simulation ROI</div>
              <div class="text-3xl font-black tracking-tighter" :class="simulationResult.roi_pct >= 0 ? 'text-success' : 'text-danger'">
                {{ simulationResult.roi_pct > 0 ? '+' : '' }}{{ simulationResult.roi_pct.toFixed(2) }}%
              </div>
              <div class="text-xs text-zinc-400 mt-1">based on {{ simulationResult.count }} trades</div>
            </div>

            <div class="space-y-3">
              <div class="flex justify-between text-xs">
                <span class="text-zinc-500">Start</span>
                <span class="text-zinc-300">{{ selection.from }}</span>
              </div>
              <div class="flex justify-between text-xs">
                <span class="text-zinc-500">End</span>
                <span class="text-zinc-300">{{ selection.to }}</span>
              </div>
            </div>
          </div>
          <div v-else class="h-32 flex flex-col items-center justify-center text-zinc-600 text-center px-4">
            <MousePointer2 class="w-8 h-8 mb-2 opacity-20" />
            <p class="text-xs">Drag on the timeline to select a simulation window</p>
          </div>
        </div>
      </aside>

      <!-- Chart Content -->
      <section class="flex-1 relative bg-background overflow-hidden flex flex-col">
        <div class="absolute top-4 left-4 z-10 flex gap-2">
           <div class="px-3 py-1.5 glass border border-zinc-700/50 rounded-lg text-xs font-medium flex items-center gap-2">
             <Activity class="w-4 h-4 text-primary" />
             Live Feed: trader.db
           </div>
        </div>
        <div class="flex-1" ref="chartContainer">
          <TimelineChart 
            ref="chartRef"
            @range-selected="onRangeSelected"
          />
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { BarChart3, Calendar, Plus, MousePointer2, Activity } from 'lucide-vue-next';
import TimelineChart from './components/TimelineChart.vue';
import axios from 'axios';

const missions = ref<any[]>([]);
const selectedMission = ref<any>(null);
const selection = ref<{from: string, to: string} | null>(null);
const simulationResult = ref({ roi_pct: 0, count: 0 });

const chartContainer = ref<HTMLElement | null>(null);
const chartRef = ref<any>(null);

const API_BASE = 'http://localhost:8000';

onMounted(async () => {
  try {
    const res = await axios.get(`${API_BASE}/missions`);
    missions.value = res.data;
  } catch (e) {
    console.error("Failed to fetch missions", e);
  }
});

const formatDate = (ts: string) => {
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
};

const onRangeSelected = async (range: {from: number, to: number}) => {
  const fromIso = new Date(range.from * 1000).toISOString();
  const toIso = new Date(range.to * 1000).toISOString();
  
  selection.value = { 
    from: fromIso.split('T')[0], 
    to: toIso.split('T')[0] 
  };
  
  try {
    const res = await axios.get(`${API_BASE}/mission/simulate`, {
      params: { start: fromIso, end: toIso }
    });
    simulationResult.value = res.data;
  } catch (e) {
    console.error("Simulation failed", e);
  }
};
</script>

<style scoped>
.glass {
  background: rgba(18, 18, 23, 0.7);
  backdrop-filter: blur(8px);
}
</style>
