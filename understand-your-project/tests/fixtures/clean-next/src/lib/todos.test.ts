import { addTodo } from "./todos";

test("adds a todo", () => {
  expect(addTodo([], "x")).toHaveLength(1);
});
