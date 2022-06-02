include("virtual_memory.jl")
using JSON, Printf

IP = 1
Fun = []
Global = GlobalMem(Persistent([], [], []), Persistent([], [], []))
CurrMem = MemoryObj(Persistent([], [], []), Temporary([], [], [], []))
MemoryStack = [CurrMem]
PointerStack = [IP]
has_address = []
pointers = [has_address]

function extract()
    try
        file = open("obj.json", "r")
        input = JSON.parse(read(file, String))
        close(file)
        input["constants"], input["modules"], input["code"]
    catch LoadError
        exit()
    end
end

function store_or_fetch(address::Int64, do_store::Bool=false, value::Any=false)
    if address ∈ ranges[1]
        do_store && return store(Global.variables, value, convert(UInt16, address - ranges[1][1] + 1), '1')
        return fetch(Global.variables, convert(UInt16, address - ranges[1][1] + 1), '1')
    elseif address ∈ ranges[2]
        do_store && return store(Global.variables, value, convert(UInt16, address - ranges[2][1] + 1), '2')
        return fetch(Global.variables, convert(UInt16, address - ranges[2][1] + 1), '2')
    elseif address ∈ ranges[3]
        do_store && return store(Global.variables, value, convert(UInt16, address - ranges[3][1] + 1), '3')
        return fetch(Global.variables, convert(UInt16, address - ranges[3][1] + 1), '3')
    elseif address ∈ ranges[4]
        do_store && return store(MemoryStack[end].persistent, value, convert(UInt16, address - ranges[4][1] + 1), '1')
        return fetch(MemoryStack[end].persistent, convert(UInt16, address - ranges[4][1] + 1), '1')
    elseif address ∈ ranges[5]
        do_store && return store(MemoryStack[end].persistent, value, convert(UInt16, address - ranges[5][1] + 1), '2')
        return fetch(MemoryStack[end].persistent, convert(UInt16, address - ranges[5][1] + 1), '2')
    elseif address ∈ ranges[6]
        do_store && return store(MemoryStack[end].persistent, value, convert(UInt16, address - ranges[6][1] + 1), '3')
        return fetch(MemoryStack[end].persistent, convert(UInt16, address - ranges[6][1] + 1), '3')
    elseif address ∈ ranges[7]
        do_store && return store(MemoryStack[end].temporary, value, convert(UInt16, address - ranges[7][1] + 1), '1')
        return fetch(MemoryStack[end].temporary, convert(UInt16, address - ranges[7][1] + 1), '1')
    elseif address ∈ ranges[8]
        do_store && return store(MemoryStack[end].temporary, value, convert(UInt16, address - ranges[8][1] + 1), '2')
        return fetch(MemoryStack[end].temporary, convert(UInt16, address - ranges[8][1] + 1), '2')
    elseif address ∈ ranges[9]
        do_store && return store(MemoryStack[end].temporary, value, convert(UInt16, address - ranges[9][1] + 1), '3')
        return fetch(MemoryStack[end].temporary, convert(UInt16, address - ranges[9][1] + 1), '3')
    elseif address ∈ ranges[10]
        do_store && return store(Global.constants, value, convert(UInt16, address - ranges[10][1] + 1), '1')
        return fetch(Global.constants, convert(UInt16, address - ranges[10][1] + 1), '1')
    elseif address ∈ ranges[11]
        do_store && return store(Global.constants, value, convert(UInt16, address - ranges[11][1] + 1), '2')
        return fetch(Global.constants, convert(UInt16, address - ranges[11][1] + 1), '2')
    elseif address ∈ ranges[12]
        do_store && return store(Global.constants, value, convert(UInt16, address - ranges[12][1] + 1), '3')
        fetch(Global.constants, convert(UInt16, address - ranges[12][1] + 1), '3')
    else
        do_store && return store(MemoryStack[end].temporary, value, convert(UInt16, address - ranges[13][1] + 1), '4')
        return fetch(MemoryStack[end].temporary, convert(UInt16, address - ranges[13][1] + 1), '4')
    end
end

function conversion(address::Int64, value::String)
    if address ∈ ranges[1] || address ∈ ranges[4] || address ∈ ranges[7] || address ∈ ranges[10]
        return parse(Int64, value)
    elseif address ∈ ranges[2] || address ∈ ranges[5] || address ∈ ranges[8] || address ∈ ranges[11]
        return parse(Float64, value)
    elseif address ∈ ranges[9]
        return parse(Bool, value)
    elseif address ∈ ranges[end]
        return parse(UInt16, value)
    else
        return value
    end
end

function operations(data::Vector{Any}, operation::String)
    left = data[2] == nothing ? 0 : store_or_fetch(data[2])
    right = store_or_fetch(data[3])
    if left === false || right === false
        println("Semantic error! Variable was never assigned a value!")
        exit()
    end
    # Arithmetic
    operation == "+" && store_or_fetch(data[4], true, left + right)
    operation == "-" && store_or_fetch(data[4], true, left - right)
    operation == "*" && store_or_fetch(data[4], true, left * right)
    try
        operation == "^" && store_or_fetch(data[4], true, left ^ right)
    catch DomainError
        println("Error! Expression returned imaginary result!")
        exit()
    end
    if operation == "/"
        result = left / right
        if result == Inf
            println("Error! Division by zero is undefined!")
            exit()
        end
        result = store_or_fetch(data[4], true, result)
    end
    operation == "++" && store_or_fetch(data[4], true, right + 1)
    operation == "--" && store_or_fetch(data[4], true, right - 1)
    # Boolean logic
    operation == ">"   && store_or_fetch(data[4], true, left > right)
    operation == ">="  && store_or_fetch(data[4], true, left >= right)
    operation == "<"   && store_or_fetch(data[4], true, left < right)
    operation == "<="  && store_or_fetch(data[4], true, left <= right)
    operation == "=="  && store_or_fetch(data[4], true, left == right)
    operation == "¬="  && store_or_fetch(data[4], true, left != right)
    operation == "and" && store_or_fetch(data[4], true, left && right)
    operation == "or"  && store_or_fetch(data[4], true, left || right)
    # Assignment
    if operation == "<-"
        data[4] ∈ ranges[end] && operations([data[1], data[2], data[3], convert( Int64, store_or_fetch(data[4]) )], operation)
        store_or_fetch(data[4], true, right)
    end
    # Array sum
    operation == "<+>" && store_or_fetch(data[4], true, left + right)
end

function printquad(msg_address::Union{Int64, Nothing}, last::Bool, jump::Bool=true)
    if msg_address == nothing
        message = ""
    else
        msg_address ∈ ranges[end] && return printquad(convert( Int64, store_or_fetch(msg_address) ), last, jump)
        message = store_or_fetch(msg_address)
        if message === false
            println("Semantic error! Variable was never assigned a value!")
            exit()
        end
    end
    if msg_address ∈ ranges[3] || msg_address ∈ ranges[6] || msg_address ∈ ranges[end-1]
        message = message[2:end-1]
    end
    last || print(message, ' ')
    last && println(message)
    jump && global PointerStack[end] += 1
end

function go_to_eval(data::Vector{Any}, type::Bool)
    result = store_or_fetch(data[2])
    if (result && type) || (!result && !type)
        global PointerStack[end] = data[4] + 1
    else
        global PointerStack[end] += 1
    end
end

function statistics(data::Vector{Real}, operation::String, storage::Int64)
    operation == "Size"       && store_or_fetch(storage, true, length(data))
    operation == "Mean"       && store_or_fetch(storage, true, mean(data))
    operation == "Median"     && store_or_fetch(storage, true, median(data))
    operation == "Mode"       && store_or_fetch(storage, true, mode(data))
    operation == "Variance"   && store_or_fetch(storage, true, var(data))
    operation == "Std"        && store_or_fetch(storage, true, std(data))
    operation == "Sum"        && store_or_fetch(storage, true, sum(data))
    operation == "Min"        && store_or_fetch(storage, true, minimum(data))
    operation == "Max"        && store_or_fetch(storage, true, maximum(data))
end

function plot_generator(data::Vector{Real}, type::String, filename::String)
    color = ["rgb(153, 9, 136)", "rgb(131, 76, 167)"]
    if type == "Histogram"
        trace = histogram(x=data, marker=attr(color=color[1], opacity=0.6, line=attr(color=color[2], width=1.5)))
    elseif type == "Violin"
        trace = violin(x=data, marker=attr(color=color[1], opacity=0.6, line=attr(color=color[2], width=1.5)))
    elseif type == "Box"
        trace = box(x=data, marker=attr(color=color[1], opacity=0.6, line=attr(color=color[2], width=1.5)))
    end
    savefig(plot(trace), filename)
end

function plot_generator(xdata::Vector{Real}, ydata::Vector{Real}, type::String, filename::String)
    color = ["rgb(153, 9, 136)", "rgb(131, 76, 167)"]
    if type == "Bar"
        trace = bar(x=xdata, y=ydata, marker=attr(color=color[1], opacity=0.6, line=attr(color=color[2], width=1.5)))
    elseif type == "Scatter"
        trace = scatter(x=xdata, y=ydata, marker=attr(color=color[1], opacity=0.6, line=attr(color=color[2], width=1.5)), mode="lines+markers")
    end
    savefig(plot(trace), filename)
end

# Main
constants, modules, instructions = extract()
for constant ∈ constants
    constant[2] ∈ ranges[end-3] && store(Global.constants, constant[1], convert(UInt16, constant[2] - ranges[end-3][1]+1), '1')
    constant[2] ∈ ranges[end-2] && store(Global.constants, constant[1], convert(UInt16, constant[2] - ranges[end-2][1]+1), '2')
    constant[2] ∈ ranges[end-1] && store(Global.constants, constant[1], convert(UInt16, constant[2] - ranges[end-1][1]+1), '3')
end
constants = nothing

while true
    current = instructions[PointerStack[end]]
    #println(current)
    # End runtime
    if current[1] == "EndProgram" break

    # Basic operations
    elseif current[1] ∈ operators
        operations(current, current[1])
        global PointerStack[end] += 1
        continue

    # I/O
    elseif current[1] == "Print"
        printquad(current[4], false)
        continue
    elseif current[1] == "LPrint"
        printquad(current[4], true)
        continue
    elseif current[1] == "Input"
        printquad(current[3], false, false)
        address = current[4]
        expected = nothing
        input = readline()
        try
            if address ∈ ranges[1] || address ∈ ranges[4] || address ∈ ranges[7] || address ∈ ranges[10]
                expected = "int"
                input = parse(Int64, input)
            elseif address ∈ ranges[2] || address ∈ ranges[5] || address ∈ ranges[8] || address ∈ ranges[11]
                expected = "float"
                input = parse(Float64, input)
            end
        catch
            @printf("Error! Type mismatch on input, expected %s.\n", expected)
            exit()
        end
        store_or_fetch(address, true, input)
        global PointerStack[end] += 1
        continue
    elseif current[1] == "Mirror"
        filename = store_or_fetch(current[2])[2:end-1]
        contents = nothing
        try
            file = open(filename, "r")
            contents = split( read(file, String)[1:end-1], ';' )
            close(file)
        catch
            println("Error file ", filename, " doesn't exist!")
            exit()
        end
        try
            if current[3] ∈ ranges[1] || current[3] ∈ ranges[4]
                contents = map(s -> parse(Int64, s), contents)
            else
                contents = map(s -> parse(Float64, s), contents)
            end
        catch
            println("Error file ", filename, " contains incorrect values or does not match the type of the storage value!")
            exit()
        end

        for val ∈ current[3]:current[4]
            store_or_fetch(val, true, contents[val - current[3] + 1])
        end
        contents = nothing
        global PointerStack[end] += 1
        continue

    # Jumps
    elseif current[1] == "Goto"
        global PointerStack[end] = current[4] + 1
        continue
    elseif current[1] == "GotoF"
        go_to_eval(current, false)
        continue
    elseif current[1] == "GotoT"
        go_to_eval(current, true)
        continue

    # Modules
    elseif current[1] == "ARE"
        for fun ∈ modules
            fun[1] != current[2] && continue
            push!(Fun, fun)
        end
        for address ∈ current[3]
            try
                if store_or_fetch(address) !== false
                    continue
                end
            catch
                store_or_fetch(address, true, nothing)
            end
            store_or_fetch(address, true, nothing)
        end
        for address ∈ current[4]
            store_or_fetch(address, true, nothing)
        end
        global PointerStack[end] += 1
        continue
    elseif current[1] == "Parameter"
        push!(Fun, store_or_fetch(current[3]))
        global PointerStack[end] += 1
        continue
    elseif current[1] == "GoSub"
        params = Fun[1][2]
        global Fun = Fun[2:end]
        NewMem = MemoryObj(Persistent([], [], []), Temporary([], [], [], []))
        push!(MemoryStack, NewMem)
        for i = 1:length(params)
            store_or_fetch(params[i][2], true, Fun[i])
        end
        global Fun = []
        global PointerStack[end] += 1
        push!(PointerStack, current[4] + 1)
        continue
    elseif current[1] == "Return"
        operations(current, "<-")
        pop!(MemoryStack)
        pop!(PointerStack)
        continue
    elseif current[1] == "EndModule"
        pop!(MemoryStack)
        pop!(PointerStack)
        global PointerStack[end] += 1
        continue

    # Arrays
    elseif current[1] == "Verify"
        val = store_or_fetch(current[2])
        inf = store_or_fetch(current[3])
        sup = store_or_fetch(current[4])
        if !(val ∈ inf:sup)
            @printf("Index out of bounds! Expected a value between %d and %d.\n", inf, sup)
            exit()
        end
        global PointerStack[end] += 1
        continue
    elseif current[1] ∈ stats
        using StatsBase

        values = [store_or_fetch(val) for val ∈ current[2]:current[3]]
        values = convert(Vector{Real}, values)
        if current[1] == "Range"
            (current[2] ∈ ranges[1] || current[2] ∈ ranges[4]) && @printf("Range: %d - %d\n", minimum(values), maximum(values))
            (current[2] ∈ ranges[2] || current[2] ∈ ranges[5]) && @printf("Range: %f - %f\n", minimum(values), maximum(values))
        else
            statistics(values, current[1], current[4])
        end
        global PointerStack[end] += 1
        continue

    # Plots
    elseif current[1] ∈ xplots
        println("Generating ", lowercase(current[1]), " plot...")
        using PlotlyJS

        values = [store_or_fetch(val) for val ∈ current[2]:current[3]]
        values = convert(Vector{Real}, values)
        filename = store_or_fetch(current[4])[2:end-1]

        plot_generator(values, current[1], filename)
        println("Plot created as ", filename, '.')
        global PointerStack[end] += 1
        continue
    elseif current[1] ∈ xyplots
        println("Generating ", lowercase(current[1]), " plot...")
        using PlotlyJS

        xvalues = [store_or_fetch(val) for val ∈ current[2]:current[3]]
        xvalues = convert(Vector{Real}, xvalues)
        global PointerStack[end] += 1
        current = instructions[PointerStack[end]]
        yvalues = [store_or_fetch(val) for val ∈ current[2]:current[3]]
        yvalues = convert(Vector{Real}, yvalues)
        filename = store_or_fetch(current[4])[2:end-1]

        plot_generator(xvalues, yvalues, current[1], filename)
        println("Plot created as ", filename, '.')
        global PointerStack[end] += 1
        continue
    end
end
