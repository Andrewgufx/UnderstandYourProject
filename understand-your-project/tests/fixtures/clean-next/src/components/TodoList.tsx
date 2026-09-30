"use client";
import { useState } from "react";
import { addTodo, type Todo } from "@/lib/todos";

export function TodoList() {
  const [todos, setTodos] = useState<Todo[]>([]);
  return (
    <ul>
      {todos.map((t) => (
        <li key={t.id}>{t.title}</li>
      ))}
      <button onClick={() => setTodos(addTodo(todos, "New"))}>Add</button>
    </ul>
  );
}
