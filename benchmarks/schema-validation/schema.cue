#Config: {
	name: =~"^[a-z][a-z0-9-]{2,31}$"
	mode: "steady" | "transient"
	steps: int & >=1 & <=10000
	grid: close({
		nx:       int & >=1
		ny:       int & >=1
		spacing_m: number & >0
	})
	if mode == "steady" {
		steps: 1
	}
}
