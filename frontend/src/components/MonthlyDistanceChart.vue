<template>
  <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
    <h2 class="font-semibold text-gray-900 mb-4">Monthly distance</h2>
    <div v-if="series[0].data.length === 0" class="text-sm text-gray-400 py-12 text-center">
      No monthly data yet.
    </div>
    <ApexChart
      v-else
      type="bar"
      height="280"
      :options="chartOptions"
      :series="series"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ApexChart from 'vue3-apexcharts'
import type { MonthlyStats, Unit } from '@/types/runs'
import { distanceLabel } from '@/utils/format'

const KM_PER_MI = 1.609344

const props = defineProps<{
  months: MonthlyStats[]
  unit: Unit
}>()

const convertedKm = (km: number) => (props.unit === 'mi' ? km / KM_PER_MI : km)

const series = computed(() => [
  {
    name: distanceLabel(props.unit),
    data: props.months.map((m) => Number(convertedKm(m.total_km).toFixed(1))),
  },
])

const monthLabels = computed(() =>
  props.months.map((m) => {
    const d = new Date(m.month)
    return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
  }),
)

const chartOptions = computed(() => ({
  chart: {
    toolbar: { show: false },
    zoom: { enabled: false },
    fontFamily: 'inherit',
    animations: { enabled: true, speed: 600 },
  },
  plotOptions: {
    bar: { borderRadius: 6, columnWidth: '60%' },
  },
  dataLabels: { enabled: false },
  colors: ['#f97316'],
  fill: {
    type: 'gradient',
    gradient: {
      shade: 'light',
      type: 'vertical',
      shadeIntensity: 0.3,
      gradientToColors: ['#fb923c'],
      opacityFrom: 1,
      opacityTo: 0.85,
      stops: [0, 100],
    },
  },
  xaxis: {
    categories: monthLabels.value,
    labels: { style: { colors: '#6b7280', fontSize: '12px' } },
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  yaxis: {
    labels: {
      style: { colors: '#6b7280', fontSize: '12px' },
      formatter: (v: number) => `${Math.round(v)} ${distanceLabel(props.unit)}`,
    },
  },
  grid: { borderColor: '#f3f4f6', strokeDashArray: 4 },
  tooltip: {
    y: {
      formatter: (v: number) => `${v.toFixed(1)} ${distanceLabel(props.unit)}`,
    },
  },
}))
</script>
