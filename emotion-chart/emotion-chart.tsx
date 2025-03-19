"use client"

import { useState } from "react"
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer } from "@/components/ui/chart"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

// Sample data with different emotions at different times
const emotionData = [
  {
    time: "9am",
    emotions: [
      { name: "Joy", value: 85, color: "hsl(var(--chart-1))" },
      { name: "Calm", value: 70, color: "hsl(var(--chart-2))" },
      { name: "Excitement", value: 65, color: "hsl(var(--chart-3))" },
      { name: "Curiosity", value: 55, color: "hsl(var(--chart-4))" },
      { name: "Gratitude", value: 50, color: "hsl(var(--chart-5))" },
    ],
  },
  {
    time: "10am",
    emotions: [
      { name: "Joy", value: 80, color: "hsl(var(--chart-1))" },
      { name: "Calm", value: 65, color: "hsl(var(--chart-2))" },
      { name: "Excitement", value: 60, color: "hsl(var(--chart-3))" },
      { name: "Curiosity", value: 50, color: "hsl(var(--chart-4))" },
      { name: "Disappointment", value: 45, color: "hsl(var(--chart-6))" },
    ],
  },
  {
    time: "11am",
    emotions: [
      { name: "Joy", value: 75, color: "hsl(var(--chart-1))" },
      { name: "Calm", value: 60, color: "hsl(var(--chart-2))" },
      { name: "Anxiety", value: 55, color: "hsl(var(--chart-7))" },
      { name: "Curiosity", value: 45, color: "hsl(var(--chart-4))" },
      { name: "Frustration", value: 40, color: "hsl(var(--chart-8))" },
    ],
  },
  {
    time: "12pm",
    emotions: [
      { name: "Joy", value: 70, color: "hsl(var(--chart-1))" },
      { name: "Calm", value: 55, color: "hsl(var(--chart-2))" },
      { name: "Excitement", value: 50, color: "hsl(var(--chart-3))" },
      { name: "Anticipation", value: 65, color: "hsl(var(--chart-9))" },
      { name: "Hunger", value: 75, color: "hsl(var(--chart-10))" },
    ],
  },
  {
    time: "1pm",
    emotions: [
      { name: "Satisfaction", value: 80, color: "hsl(var(--chart-11))" },
      { name: "Calm", value: 70, color: "hsl(var(--chart-2))" },
      { name: "Contentment", value: 75, color: "hsl(var(--chart-12))" },
      { name: "Relaxation", value: 65, color: "hsl(var(--chart-13))" },
      { name: "Joy", value: 60, color: "hsl(var(--chart-1))" },
    ],
  },
]

// Transform data for chart display
const transformDataForChart = (data) => {
  if (!data || !Array.isArray(data)) return []

  const result = []

  data.forEach((timeSlot) => {
    if (!timeSlot || !timeSlot.emotions || !Array.isArray(timeSlot.emotions)) return

    const entry = { time: timeSlot.time || "Unknown" }

    timeSlot.emotions.forEach((emotion) => {
      if (emotion && emotion.name) {
        entry[emotion.name] = emotion.value || 0
      }
    })

    result.push(entry)
  })

  return result
}

// Get all unique emotions across all time slots
const getAllEmotions = (data) => {
  if (!data || !Array.isArray(data)) return []

  const emotionsSet = new Set()

  data.forEach((timeSlot) => {
    if (!timeSlot || !timeSlot.emotions || !Array.isArray(timeSlot.emotions)) return

    timeSlot.emotions.forEach((emotion) => {
      if (emotion && emotion.name) {
        emotionsSet.add(emotion.name)
      }
    })
  })

  return Array.from(emotionsSet)
}

// Create color map for all emotions
const createColorMap = (data) => {
  if (!data || !Array.isArray(data)) return {}

  const colorMap = {}

  data.forEach((timeSlot) => {
    if (!timeSlot || !timeSlot.emotions || !Array.isArray(timeSlot.emotions)) return

    timeSlot.emotions.forEach((emotion) => {
      if (emotion && emotion.name) {
        if (!colorMap[emotion.name]) {
          colorMap[emotion.name] = emotion.color || "hsl(var(--chart-1))"
        }
      }
    })
  })

  return colorMap
}

export default function EmotionChart() {
  const [viewType, setViewType] = useState("all")
  const [selectedTime, setSelectedTime] = useState("all")

  const chartData = transformDataForChart(emotionData)
  const allEmotions = getAllEmotions(emotionData)
  const colorMap = createColorMap(emotionData)

  // Filter data based on selected time
  const filteredData = selectedTime === "all" ? chartData : chartData.filter((item) => item.time === selectedTime)

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Emotion Tracking</CardTitle>
        <CardDescription>Visualizing the top 5 emotions at different times of the day</CardDescription>
        <div className="flex flex-wrap gap-4 pt-4">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium">View:</span>
            <Select value={viewType} onValueChange={setViewType}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select view" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Emotions</SelectItem>
                <SelectItem value="top5">Top 5 Only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium">Time:</span>
            <Select value={selectedTime} onValueChange={setSelectedTime}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select time" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Times</SelectItem>
                {emotionData.map((item) => (
                  <SelectItem key={item.time} value={item.time}>
                    {item.time}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[400px]">
          <ChartContainer>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={filteredData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="time" angle={-45} textAnchor="end" height={60} tickMargin={20} />
                <YAxis label={{ value: "Intensity", angle: -90, position: "insideLeft" }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend verticalAlign="top" height={36} />

                {allEmotions.map((emotion) => (
                  <Bar
                    key={emotion}
                    dataKey={emotion}
                    fill={colorMap[emotion]}
                    name={emotion}
                    stackId={viewType === "stacked" ? "a" : undefined}
                    hide={viewType === "top5" && !isInTop5(emotion, selectedTime)}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </ChartContainer>
        </div>
      </CardContent>
    </Card>
  )

  // Helper function to check if an emotion is in the top 5 for the selected time
  function isInTop5(emotion, selectedTime) {
    if (selectedTime === "all") return true

    const timeData = emotionData.find((item) => item && item.time === selectedTime)
    if (!timeData || !timeData.emotions || !Array.isArray(timeData.emotions)) return false

    return timeData.emotions.some((e) => e && e.name === emotion)
  }

  // Custom tooltip component
  function CustomTooltip({ active, payload, label }) {
    if (!active || !payload || !Array.isArray(payload) || payload.length === 0) return null

    // Sort emotions by value for this time slot
    const sortedEmotions = [...payload]
      .filter((entry) => entry && entry.value > 0)
      .sort((a, b) => (b?.value || 0) - (a?.value || 0))

    return (
      <div className="rounded-lg border bg-background p-2 shadow-sm">
        <div className="grid gap-2">
          <div className="font-semibold">{label || "Unknown"}</div>
          <div className="grid gap-1">
            {sortedEmotions.map((entry, index) => (
              <div key={index} className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full" style={{ backgroundColor: entry?.fill || "gray" }} />
                <span className="text-sm">
                  {entry?.name || "Unknown"}: {entry?.value || 0}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }
}

