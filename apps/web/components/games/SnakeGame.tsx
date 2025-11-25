'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

const GRID_SIZE = 20
const CELL_SIZE = 20
const INITIAL_SNAKE = [{ x: 10, y: 10 }]
const INITIAL_DIRECTION = { x: 1, y: 0 }
const GAME_SPEED = 150

type Position = { x: number; y: number }
type Direction = { x: number; y: number }

export default function SnakeGame() {
  const [snake, setSnake] = useState<Position[]>(INITIAL_SNAKE)
  const [food, setFood] = useState<Position>({ x: 15, y: 15 })
  const [direction, setDirection] = useState<Direction>(INITIAL_DIRECTION)
  const [gameOver, setGameOver] = useState(false)
  const [score, setScore] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const [gameStarted, setGameStarted] = useState(false)
  const directionRef = useRef<Direction>(INITIAL_DIRECTION)
  const gameLoopRef = useRef<NodeJS.Timeout | null>(null)

  // Generate random food position
  const generateFood = useCallback((snakeBody: Position[] = []): Position => {
    let newFood: Position
    do {
      newFood = {
        x: Math.floor(Math.random() * GRID_SIZE),
        y: Math.floor(Math.random() * GRID_SIZE),
      }
    } while (snakeBody.some((segment) => segment.x === newFood.x && segment.y === newFood.y))
    return newFood
  }, [])

  // Check collision
  const checkCollision = useCallback((head: Position, body: Position[]): boolean => {
    // Check wall collision
    if (head.x < 0 || head.x >= GRID_SIZE || head.y < 0 || head.y >= GRID_SIZE) {
      return true
    }
    // Check self collision
    return body.some((segment) => segment.x === head.x && segment.y === head.y)
  }, [])

  // Game loop
  const gameLoop = useCallback(() => {
    if (isPaused || gameOver || !gameStarted) return

    setSnake((prevSnake) => {
      const newHead = {
        x: prevSnake[0].x + directionRef.current.x,
        y: prevSnake[0].y + directionRef.current.y,
      }

      // Check collision
      if (checkCollision(newHead, prevSnake)) {
        setGameOver(true)
        return prevSnake
      }

      const newSnake = [newHead, ...prevSnake]

      // Check if food is eaten
      if (newHead.x === food.x && newHead.y === food.y) {
        setScore((prev) => prev + 1)
        setFood((prevFood) => generateFood(newSnake))
        return newSnake
      }

      // Remove tail
      newSnake.pop()
      return newSnake
    })
  }, [food, isPaused, gameOver, gameStarted, checkCollision, generateFood])

  // Handle keyboard input
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (!gameStarted && e.key !== ' ') return

      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault()
          if (directionRef.current.y === 0) {
            directionRef.current = { x: 0, y: -1 }
            setDirection({ x: 0, y: -1 })
          }
          break
        case 'ArrowDown':
          e.preventDefault()
          if (directionRef.current.y === 0) {
            directionRef.current = { x: 0, y: 1 }
            setDirection({ x: 0, y: 1 })
          }
          break
        case 'ArrowLeft':
          e.preventDefault()
          if (directionRef.current.x === 0) {
            directionRef.current = { x: -1, y: 0 }
            setDirection({ x: -1, y: 0 })
          }
          break
        case 'ArrowRight':
          e.preventDefault()
          if (directionRef.current.x === 0) {
            directionRef.current = { x: 1, y: 0 }
            setDirection({ x: 1, y: 0 })
          }
          break
        case ' ':
          e.preventDefault()
          if (gameOver) {
            resetGame()
          } else if (gameStarted) {
            setIsPaused((prev) => !prev)
          } else {
            setGameStarted(true)
          }
          break
      }
    }

    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [gameOver, gameStarted])

  // Start game loop
  useEffect(() => {
    if (gameStarted && !gameOver && !isPaused) {
      gameLoopRef.current = setInterval(gameLoop, GAME_SPEED)
    } else {
      if (gameLoopRef.current) {
        clearInterval(gameLoopRef.current)
        gameLoopRef.current = null
      }
    }

    return () => {
      if (gameLoopRef.current) {
        clearInterval(gameLoopRef.current)
      }
    }
  }, [gameStarted, gameOver, isPaused, gameLoop])

  // Reset game
  const resetGame = () => {
    const initialSnake = INITIAL_SNAKE
    setSnake(initialSnake)
    setFood(generateFood(initialSnake))
    setDirection(INITIAL_DIRECTION)
    directionRef.current = INITIAL_DIRECTION
    setGameOver(false)
    setScore(0)
    setIsPaused(false)
    setGameStarted(true)
  }

  // Render grid cell
  const renderCell = (x: number, y: number) => {
    const isSnakeHead = snake[0]?.x === x && snake[0]?.y === y
    const isSnakeBody = snake.slice(1).some((segment) => segment.x === x && segment.y === y)
    const isFood = food.x === x && food.y === y

    let cellClass = 'border border-gray-200'
    if (isSnakeHead) {
      cellClass = 'bg-green-600 rounded-sm'
    } else if (isSnakeBody) {
      cellClass = 'bg-green-500 rounded-sm'
    } else if (isFood) {
      cellClass = 'bg-red-500 rounded-full'
    } else {
      cellClass = 'bg-gray-50 border border-gray-200'
    }

    return (
      <div
        key={`${x}-${y}`}
        className={cellClass}
        style={{ width: CELL_SIZE, height: CELL_SIZE }}
      />
    )
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-green-50 to-blue-50 p-4">
      <div className="bg-white rounded-lg shadow-2xl p-6 max-w-2xl w-full">
        <div className="text-center mb-6">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">🐍 Змійка</h1>
          <div className="flex items-center justify-center gap-6 text-lg">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-700">Рахунок:</span>
              <span className="text-green-600 font-bold text-2xl">{score}</span>
            </div>
            {isPaused && (
              <span className="text-yellow-600 font-semibold animate-pulse">⏸ Пауза</span>
            )}
          </div>
        </div>

        <div className="flex justify-center mb-4">
          <div
            className="grid gap-0 border-4 border-gray-800 rounded-lg p-2 bg-gray-100"
            style={{
              gridTemplateColumns: `repeat(${GRID_SIZE}, ${CELL_SIZE}px)`,
              width: GRID_SIZE * CELL_SIZE + 16,
            }}
          >
            {Array.from({ length: GRID_SIZE * GRID_SIZE }, (_, i) => {
              const x = i % GRID_SIZE
              const y = Math.floor(i / GRID_SIZE)
              return renderCell(x, y)
            })}
          </div>
        </div>

        {!gameStarted && (
          <div className="text-center mt-6 p-6 bg-blue-50 rounded-lg">
            <p className="text-xl font-semibold text-gray-700 mb-4">
              Натисніть пробіл або кнопку нижче, щоб почати гру
            </p>
            <button
              onClick={() => setGameStarted(true)}
              className="px-6 py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700 transition-colors shadow-lg"
            >
              Почати гру
            </button>
          </div>
        )}

        {gameOver && (
          <div className="text-center mt-6 p-6 bg-red-50 rounded-lg border-2 border-red-200">
            <p className="text-2xl font-bold text-red-600 mb-2">Гра закінчена!</p>
            <p className="text-lg text-gray-700 mb-4">Ваш рахунок: {score}</p>
            <button
              onClick={resetGame}
              className="px-6 py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700 transition-colors shadow-lg"
            >
              Грати знову
            </button>
          </div>
        )}

        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="font-semibold text-gray-700 mb-2">Керування:</h3>
          <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
            <div>⬆️⬇️⬅️➡️ Стрілки - рух</div>
            <div>⏸ Пробіл - пауза/старт</div>
          </div>
        </div>
      </div>
    </div>
  )
}
