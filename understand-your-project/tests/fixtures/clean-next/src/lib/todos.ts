export type Todo = { id: number; title: string; done: boolean };

export function addTodo(todos: Todo[], title: string): Todo[] {
  return [...todos, { id: todos.length + 1, title, done: false }];
}
