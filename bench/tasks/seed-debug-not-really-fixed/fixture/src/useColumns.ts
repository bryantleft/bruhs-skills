import { useEffect, useState } from "react";
import { columnsFor } from "./layout";

export function useColumns(): 1 | 2 {
  const [columns, setColumns] = useState(() => columnsFor(window.innerWidth));
  useEffect(() => {
    const onResize = () => setColumns(columnsFor(window.innerWidth));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return columns;
}
