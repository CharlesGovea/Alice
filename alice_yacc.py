import ply.yacc as yacc
from sys import argv
from collections.abc import Iterable
from alice_lex import tokens
from sem_cube import get_result
from structs import *

#--------------------------Environment Setup------------------------------------
tmpvar_n = -1
quad_count = -1
fun = False
dims = False
dim = None
recursive_calls = []

S = stacks()
funDir = mdl_dir()
constants = cte_table()
variables = var_table()
quadruples = quadruple_list()

memory = memory()
env = 'global'

#--------------------------Auxiliary Functions----------------------------------
def find(ID, list_name):
    if list_name == 'dec':
        if not variables.var_list:
            return False
        for var in variables.var_list:
            if var.ID != ID:
                continue
            else:
                if env != 'global' and (var.v_address >= 5000 and var.v_address < 10000):
                    return var
                elif env == 'global' and (var.v_address >= 0 and var.v_address < 5000):
                    return var
        return False

    elif list_name == 'cte':
        if not constants.cte_list:
            return False
        for constant in constants.cte_list:
            if constant.ID == ID:
                return constant
        return False

    elif list_name == 'var':
        if not variables.var_list:
            return False
        var_list = variables.var_list.copy()
        var_list.reverse()
        for var in var_list:
            if var.ID != ID:
                continue
            else:
                return var
        return False

def quad_gen(quad):
    global quad_count
    new_quad = quadruple(*quad)
    quadruples.append(new_quad)
    quad_count += 1

def quad_address(temp=None):
    if temp == None:
        temp = S.Symbols.pop()
    token = find(temp, 'cte')
    if not token:
        token = find(temp, 'var')
    if not token:
        print(f"Error! Variable '{temp}' wasn't declared!")
        quit()
    return token.v_address

def temporary_handler(type, append=True, name=False):
    if type == 0:
        address = memory.tmpi[0] + memory.tmpi[1]
        if address >= memory.tmpf[0]:
            print(f'Error! Too many temporal integer variables!')
            quit()
        memory.tmpi[1] += 1
        typetxt = 'int'
    elif type == 1:
        address = memory.tmpf[0] + memory.tmpf[1]
        if address >= memory.tmpb[0]:
            print(f'Error! Too many temporal float variables!')
            quit()
        memory.tmpf[1] += 1
        typetxt = 'float'
    elif type == 3:
        address = memory.tmpb[0] + memory.tmpb[1]
        if address >= memory.ctei[0]:
            print(f'Error! Too many temporal boolean variables!')
            quit()
        memory.tmpb[1] += 1
        typetxt = 'bool'
    else:
        address = memory.ptrs[0] + memory.ptrs[1]
        if address >= 32000:
            print(f'Error! Too many pointers!')
            quit()
        memory.ptrs[1] += 1
        typetxt = 'pointer'

    if not name:
        global tmpvar_n
        tmpvar_n += 1
        if type == 4:
            tn = 'ptr' + str(tmpvar_n)
        else:
            tn = 't' + str(tmpvar_n)
    else:
        tn = name
    if append:
        S.Types.append((type, typetxt))
        S.Symbols.append(tn)

    new_var = var_object(tn, (type, typetxt), address, [[0, 0], 1])
    variables.append(new_var)
    return address

def constant_handler(p, cte, append=True):
    if append:
        S.Symbols.append(p[-1])
        S.Types.append(cte)
    if find(p[-1], 'cte') != False:
        return find(p[-1], 'cte')
    else:
        if cte[0] == 0:
            address = memory.ctei[0] + memory.ctei[1]
            if address >= memory.ctef[0]:
                print(f'Error! Too many integer literals!')
                quit()
            memory.ctei[1] += 1
        elif cte[0] == 1:
            address = memory.ctef[0] + memory.ctef[1]
            if address >= memory.ctes[0]:
                print(f'Error! Too many float literals!')
                quit()
            memory.ctef[1] += 1
        else:
            address = memory.ctes[0] + memory.ctes[1]
            if address >= memory.ptrs[0]:
                print(f'Error! Too many string literals!')
                quit()
            memory.ctes[1] += 1

        new_cte = cte_object(p[-1], address)
        constants.append(new_cte)

def expression_handler(p, operator):
    length = len(S.Operators)
    try:
        size = length - 1 - S.Operators.index('(')
    except ValueError:
        size = length

    if size > 0 and S.Operators[length - 1] == operator:
        type_der = S.Types.pop()
        type_izq = S.Types.pop()
        operator = S.Operators.pop()

        res = get_result((operator, type_izq[0], type_der[0]))
        if res is False:
            if operator == 'and' or operator == 'or':
                print(f'Semantic error! Expected two bool operands, got {type_izq[1]} and {type_der[1]}!')
            elif operator in ['==', '¬=', '<', '<=', '>', '>=']:
                print(f'Semantic error! Cannot compare {type_izq[1]} and {type_der[1]}!')
            else:
                print(f'Semantic error! Cannot perform arithmetic operations between {type_izq[1]} and {type_der[1]}!')
            quit()

        der_address = quad_address()
        izq_address = quad_address()
        tn = temporary_handler(res)
        quad_gen((operator, izq_address, der_address, tn))

def unary_handler(p, operator):
    length = len(S.Operators)
    try:
        size = length - 1 - S.Operators.index('(')
    except ValueError:
        size = length

    if size > 0 and S.Operators[length - 1] == operator:
        type_der = S.Types.pop()
        operator = S.Operators.pop()

        if operator == '-':
            if type_der[0] > 1:
                print(f'Semantic error! {type_der[1]} data cannot be turned negative!')
                quit()
            else:
                res = type_der[0]
        else:
            res = get_result((operator, type_der[0]))
            if res is False:
                print(f'Semantic error! Cannot perform arithmetic increment or decrease on {type_der[1]}!')
                quit()

        der_address = quad_address()
        if operator == '-' or (der_address >= 26000 and der_address < 31000):
            tn = temporary_handler(res)
            quad_gen((operator, None, der_address, tn))
        else:
            S.Symbols.append(p[-3])
            S.Types.append(type_der)
            quad_gen((operator, None, der_address, der_address))

def dimension_tracker(dim):
    val = quad_address(S.Symbols[-1])
    curr = dims.arr_size if type(dims.arr_size[1]) != list else dims.arr_size[0]
    izq = find(curr[0][0], 'cte')
    der = find(curr[0][1], 'cte')
    quad_gen(('Verify', val, izq.v_address, der.v_address))

    if type(dims.arr_size[1]) == list:
        aux = [S.Symbols.pop(), S.Types.pop()]
        temp = temporary_handler(0)
        size = find(curr[0][1], 'cte')
        quad_gen(('*', val, size.v_address, temp))
    if dim > 1:
        aux2 = [quad_address(S.Symbols.pop()), S.Types.pop()]
        aux1 = [quad_address(S.Symbols.pop()), S.Types.pop()]
        temp = temporary_handler(0)
        quad_gen(('+', aux1[0], aux2[0], temp))

def call_solver(ARE, IDList, aux, modify=False):
    addresses = [[], []]
    ARE[2] = addresses[0]
    ARE[3] = addresses[1]
    params = []
    if fun.size != None:
        locals = fun.size[0].copy()
    else:
        temp = [IDList, aux.copy()]
    for i in range(len(IDList)):
        prototype = fun.prototyping[i][0]
        param = aux.pop()
        if prototype != param[1][0]:
            print(f"Error! Type mismatch in function call to '{fun.ID}' with parameter {i+1}!")
            quit()

        var = find(param[0], 'cte')
        if not var:
            var = find(param[0], 'var')
        if fun.size != None and var.v_address >= 6000 and var.v_address < 11000:
            locals[prototype] -= 1
            addresses[0].append(var.v_address)
        if not modify:
            params.append(('Parameter', None, var.v_address, i+1))

    if fun.size != None:
        for i in range(len(locals)):
            if locals[i] == 0:
                continue
            for j in range(locals[i]):
                if i == 0:
                    address = memory.lcli[0] + memory.lcli[1]
                    if address >= memory.lclf[0]:
                        print(f'Error! Too many local integer variables!')
                        quit()
                    memory.lcli[1] +=  1
                elif i == 1:
                    address = memory.lclf[0] + memory.lclf[1]
                    if address >= memory.lcls[0]:
                        print(f'Error! Too many local float variables!')
                        quit()
                    memory.lclf[1] += 1
                else:
                    address = memory.lcls[0] + memory.lcls[1]
                    if address >= memory.tmpi[0]:
                        print(f'Error! Too many local string variables!')
                        quit()
                    memory.lcls[1] +=  1
                addresses[0].append(address)
        temps = fun.size[1]
        for i in range(len(temps)):
            if temps[i] == 0:
                continue
            for j in range(temps[i]):
                address = temporary_handler(i, False)
                addresses[1].append(address)
        if not modify:
            quad_gen(ARE)
    else:
        quad_gen(('ARE', fun.ID, None, None))
        recursive_calls.append([quad_count, temp])

    if not modify:
        for quad in params:
            quad_gen(quad)
        quad_gen(('GoSub', None, None, fun.beginning))
    else:
        return ARE

def get_IDs(IDList):
     for item in IDList:
         if isinstance(item, Iterable) and not isinstance(item, str):
             for x in get_IDs(item):
                 yield x
         else:
             yield item

def end_yacc():
    export(quadruples, constants, funDir)

#---------------------------Program Structure-----------------------------------
def p_program(p):
    '''
    program : BEGIN beginprog ID lclenv_setup COLON global ENDPROG endprog
    '''
    end_yacc()

def p_global(p):
    '''
    global : module global
           | declaration global
           | main
    '''

def p_main(p):
    '''
    main : MAIN lclenv_setup stmtblock
    '''

def p_stmtblock(p):
    '''
    stmtblock : COLON initstmt END
    '''

def p_initstmt(p):
    '''
    initstmt : stmt stmtchain
             | empty
    '''

def p_stmtchain(p):
    '''
    stmtchain : stmtchain stmt
              | empty
    '''

def p_stmt(p):
    '''
    stmt : assignment
         | conditional
         | print
         | input
         | iteration
         | plot
         | declaration
         | mirror
         | expression popexpr
         | return
    '''

#--------------------------Complex Statements-----------------------------------
def p_conditional(p):
    '''
    conditional : IF expr neuralgic_if THEN stmtblock neuralgic_cond
                | IF expr neuralgic_if THEN COLON initstmt ELSE neuralgic_else stmtblock neuralgic_cond
    '''

def p_iteration(p):
    '''
    iteration : while
              | do_while
              | for
    '''

def p_while(p):
    '''
    while : WHILE neuralgic_while expr while_expr stmtblock while_end
    '''

def p_do_while(p):
    '''
    do_while : DO neuralgic_dw stmtblock WHILE expression dw_end
    '''

def p_for(p):
    '''
    for : FOR ID for_id ASSIGN expr for_expr COLON expr neuralgic_for stmtblock for_end
    '''

#-------------------------------Module------------------------------------------
def p_module(p):
    '''
    module : MODULE ID TYPE_ASSIGN mdl_type lclenv_setup LPAREN params neuralgic_params RPAREN stmtblock lclenv_end
    '''

def p_mdl_type(p):
    '''
    mdl_type : VOID
             | type
    '''
    p[0] = p[1]

def p_params(p):
    '''
    params : ID TYPE_ASSIGN type rparams
           | empty
    '''
    if len(p) > 2:
        if p[4] == None:
            p[0] = p[1], p[3]
        else:
            p[0] = p[1], p[3], p[4]
    else:
        p[0] = p[1]

def p_rparams(p):
    '''
    rparams : rparams COMA ID TYPE_ASSIGN type
            | empty
    '''
    if len(p) > 2:
        p[0] = p[1], p[3], p[5]
    else:
        p[0] = p[1]

#-----------------------------Variables-----------------------------------------
def p_assignment(p):
    '''
    assignment : variable ASSIGN expression neuralgic_assign
    '''

def p_declaration(p):
    '''
    declaration : LET ID others TYPE_ASSIGN type idxsize neuralgic_dec SEMICOLON
    '''

def p_others(p):
    '''
    others : others COMA ID
           | empty
    '''
    if len(p) > 2:
        if p[1] == None:
            p[0] = p[3]
        p[0] = p[1], p[3]
    else:
        p[0] = p[1]

def p_idxsize(p):
    '''
    idxsize : L_SBRKT CTE_I matrix R_SBRKT
            | empty
    '''
    if len(p) > 2:
        p[0] = p[2], p[3]
    else:
        p[0] = p[1]

def p_matrix(p):
    '''
    matrix : COMA CTE_I
           | empty
    '''
    if len(p) > 2:
        p[0] = p[2]
    else:
        p[0] = p[1]

#------------------------------Expressions--------------------------------------
def p_expression(p):
    '''
    expression : expr SEMICOLON
    '''
    p[0] = p[1]

def p_expr(p):
    '''
    expr : andexpr
         | expr OR neuralgic_opr andexpr neuralgic_expr
    '''
    p[0] = p[1]

def p_andexpr(p):
    '''
    andexpr : eqlexpr
            | andexpr AND neuralgic_opr eqlexpr neuralgic_expr
    '''
    p[0] = p[1]

def p_eqlexpr(p):
    '''
    eqlexpr : relexpr
            | eqlexpr eqop neuralgic_opr relexpr neuralgic_expr
    '''
    p[0] = p[1]

def p_eqop(p):
    '''
    eqop : EQ
         | NE
    '''
    p[0] = p[1]

def p_relexpr(p):
    '''
    relexpr : sumexpr
            | relexpr relop neuralgic_opr sumexpr neuralgic_expr
    '''
    p[0] = p[1]

def p_relop(p):
    '''
    relop : LE
          | LT
          | GE
          | GT
    '''
    p[0] = p[1]

def p_sumexpr(p):
    '''
    sumexpr : term
            | sumexpr sumop neuralgic_opr term neuralgic_expr
    '''
    p[0] = p[1]

def p_sumop(p):
    '''
    sumop : PLUS
          | MINUS
    '''
    p[0] = p[1]

def p_term(p):
    '''
    term : unary
         | term mulop neuralgic_opr unary neuralgic_expr
    '''
    p[0] = p[1]

def p_mulop(p):
    '''
    mulop : EXPONENT
          | MULTIPLY
          | DIVIDE
    '''
    p[0] = p[1]

def p_unary(p):
    '''
    unary : postfix
          | MINUS neuralgic_opr postfix neuralgic_unary
    '''
    if len(p) > 2:
        p[0] = p[3]
    else:
        p[0] = p[1]

def p_postfix(p):
    '''
    postfix : factor
            | factor postop neuralgic_opr neuralgic_unary
    '''
    p[0] = p[1]

def p_postop(p):
    '''
    postop : ADD
           | DECREASE
    '''
    p[0] = p[1]

def p_factor(p):
    '''
    factor : LPAREN neuralgic_opr expr RPAREN neuralgic_paren
           | value
           | variable
           | systemdef neuralgic_stats
           | call add_call
    '''
    if len(p) > 3:
        p[0] = p[3]
    else:
        p[0] = p[1]

def p_value(p):
    '''
    value : CTE_I neuralgic_int
          | CTE_F neuralgic_float
          | CTE_STRING neuralgic_str
    '''
    p[0] = p[1]

def p_variable(p):
    '''
    variable : ID neuralgic_var
             | ID neuralgic_var L_SBRKT neuralgic_array expr evaluate_dimension R_SBRKT end_dimensions
             | ID neuralgic_var L_SBRKT neuralgic_array expr evaluate_dimension COMA expr neuralgic_matrix R_SBRKT end_dimensions
    '''
    if len(p) == 9:
        p[0] = p[1], p[5], p[7]
    elif len(p) == 11:
        p[0] = p[1], p[5], p[7], p[8], p[9]
    else:
        p[0] = p[1]

#----------------------------System Functions-----------------------------------
def p_print(p):
    '''
    print : PRINT LPAREN funparam RPAREN neuralgic_print SEMICOLON
    '''

def p_funparam(p):
    '''
    funparam : expr auxparams
             | empty
    '''
    if len(p) > 2:
        if p[2] == None:
            p[0] = p[1]
        p[0] = p[1], p[2]
    else:
        p[0] = p[1]

def p_auxparams(p):
    '''
    auxparams : auxparams COMA expr
              | empty
    '''
    if len(p) > 2:
        if p[1] == None:
            p[0] = p[3]
        p[0] = p[1], p[3]
    else:
        p[0] = p[1]

def p_input(p):
    '''
    input : INPUT LPAREN expr COMA ID RPAREN neuralgic_input SEMICOLON
    '''

def p_mirror(p):
    '''
    mirror : MIRROR LPAREN expr COMA ID RPAREN SEMICOLON neuralgic_mirror
    '''

def p_plot(p):
    '''
    plot : x_plot
         | xy_plot
    '''

def p_x_plot(p):
    '''
    x_plot : HIST LPAREN ID COMA CTE_STRING RPAREN SEMICOLON neuralgic_xplot
           | VIOLIN LPAREN ID COMA CTE_STRING RPAREN SEMICOLON neuralgic_xplot
           | BOXPLOT LPAREN ID COMA CTE_STRING RPAREN SEMICOLON neuralgic_xplot
    '''

def p_xy_plot(p):
    '''
    xy_plot : BAR LPAREN ID COMA ID COMA CTE_STRING RPAREN SEMICOLON neuralgic_xyplot
            | SCATTER LPAREN ID COMA ID COMA CTE_STRING RPAREN SEMICOLON neuralgic_xyplot
    '''

def p_systemdef(p):
    '''
    systemdef : SIZE LPAREN ID RPAREN
              | MEAN LPAREN ID RPAREN
              | MEDIAN LPAREN ID RPAREN
              | MODE LPAREN ID RPAREN
              | VARIANCE LPAREN ID RPAREN
              | STD LPAREN ID RPAREN
              | RANGE LPAREN ID RPAREN
              | SUM LPAREN ID RPAREN
              | MIN LPAREN ID RPAREN
              | MAX LPAREN ID RPAREN
    '''
    p[0] = p[1], p[3]

def p_call(p):
    '''
    call : ID verify_ID LPAREN funparam neuralgic_call RPAREN
    '''
    p[0] = p[1], p[3]

#-------------------------------Typed Rules-------------------------------------
def p_return(p):
    '''
    return : RETURN expression neuralgic_return
    '''

def p_type(p):
    '''
    type : INT
         | FLOAT
         | STRING
    '''
    p[0] = p[1]

#---------------------------Neuralgic Rules-------------------------------------
def p_lclenv_setup(p):
    '''
    lclenv_setup :
    '''
    if p[-3] == 'begin':
        program = mdl_object(p[-1], 'void', quad_count, variables, None, None)
        funDir.append(program)
    else:
        global env
        env = p[-1]
        if env != 'main':
            if env in ['int', 'float', 'string']:
                type = None
                address = None
                for module in funDir.modules:
                    if module.ID == p[-3]:
                        print(f"Error! Module '{p[-3]}' already exists!")
                        quit()
                if find(p[-3], 'var') != False:
                    print(f"Error! Cannot create module '{p[-3]}', name already reserved!")
                    quit()

                if env == 'int':
                    type = (0, env)
                    address = memory.gbli[0] + memory.gbli[1]
                    if address >= memory.gblf[0]:
                        print(f'Error! Too many global integer variables!')
                        quit()
                    memory.gbli[1] += 1
                elif env == 'float':
                    type = (1, env)
                    address = memory.gblf[0] + memory.gblf[1]
                    if address >= memory.gbls[0]:
                        print(f'Error! Too many global float variables!')
                        quit()
                    memory.gblf[1] += 1
                elif env == 'string':
                    type = (2, env)
                    address = memory.gbls[0] + memory.gbls[1]
                    if address >= memory.lcli[0]:
                        print(f'Error! Too many global string variables!')
                        quit()
                    memory.gbls[1] += 1
                new_var = var_object(p[-3], type, address, [[0, 0], 1])
                variables.append(new_var)
            program = mdl_object(p[-3], env, quad_count + 1, None, None, None)
            funDir.append(program)
        else:
            goback = S.Jumps.pop()
            quadruples.quadruples[goback].storage = quad_count + 1

def p_lclenv_end(p):
    '''
    lclenv_end :
    '''
    global env
    global tmpvar_n
    tmpvar_n = -1
    env = 'global'
    size = [[0, 0, 0],[0, 0, 0]]
    temp = var_table()
    aux = []
    temp.var_list = variables.copy()
    for i in range(len(temp.var_list)):
        if temp.var_list[i].v_address >= 6000 and temp.var_list[i].v_address < 8000:
            size[0][0] += 1
            continue
        elif temp.var_list[i].v_address >= 8000 and temp.var_list[i].v_address < 10000:
            size[0][1] += 1
            continue
        elif temp.var_list[i].v_address >= 10000 and temp.var_list[i].v_address < 11000:
            size[0][2] += 1
            continue
        elif temp.var_list[i].v_address >= 11000 and temp.var_list[i].v_address < 16000:
            size[1][0] += 1
            continue
        elif temp.var_list[i].v_address >= 16000 and temp.var_list[i].v_address < 21000:
            size[1][1] += 1
            continue
        elif temp.var_list[i].v_address >= 21000 and temp.var_list[i].v_address < 26000:
            size[1][2] += 1
            continue
        aux.append(temp.var_list[i])

    funDir.modules[-1].variables = temp
    funDir.modules[-1].size = size
    if not recursive_calls:
        pass
    else:
        for i in range(len(recursive_calls)):
            call = recursive_calls[i][0]
            info = recursive_calls[i][1]
            curr = quadruples.quadruples[call]
            ARE = [curr.operation, curr.operand1, curr.operand2, curr.storage]
            ARE = call_solver(ARE, *info, modify=True)
            curr.operand2 = ARE[2]
            curr.storage = ARE[3]

    memory.clear()
    variables.var_list = aux
    quad_gen(('EndModule', None, None, None))

def p_beginprog(p):
    '''
    beginprog :
    '''
    quad_gen(('Goto', None, None, 'Main'))
    S.Jumps.append(quad_count)

def p_endprog(p):
    '''
    endprog :
    '''
    quad_gen(('EndProgram', None, None, None))

def p_popexpr(p):
    '''
    popexpr :
    '''
    if not S.Symbols:
        return
    S.Symbols.pop()
    S.Types.pop()

def p_neuralgic_assign(p):
    '''
    neuralgic_assign :
    '''
    der_address = quad_address()
    izq_address = quad_address()
    type_der = S.Types.pop()
    type_izq = S.Types.pop()
    res = get_result((p[-2], type_izq[0], type_der[0]))
    if res is False:
        print(f'Semantic error! Type mismatch: Got {type_izq[1]} and {type_der[1]}!')
        quit()
    quad_gen((p[-2], None, der_address, izq_address))

def p_neuralgic_dec(p):
    '''
    neuralgic_dec :
    '''
    if p[-1] == None:
        arr_size = [[0, 0], 1]
    elif p[-1][1] == None:
        dim1 = int(p[-1][0])
        constant_handler([dim1 - 1], (0, 'int'), False)
        constant_handler([1], (0, 'int'), False)
        constant_handler([0], (0, 'int'), False)
        if dim1 <= 1:
            print(f"Error! Array's size isn't valid!")
            quit()
        arr_size = [[0, dim1 - 1], 1]
    else:
        dim1 = int(p[-1][0])
        dim2 = int(p[-1][1])
        constant_handler([dim1 - 1], (0, 'int'), False)
        constant_handler([dim2 - 1], (0, 'int'), False)
        constant_handler([dim2], (0, 'int'), False)
        constant_handler([1], (0, 'int'), False)
        constant_handler([0], (0, 'int'), False)
        if dim1 <= 1 or dim2 <= 1:
            print(f"Error! Matrix's {'1st' if dim1 <= 0 else '2nd'} dimension's value isn't valid!")
            quit()
        tsize = dim1 * dim2
        arr_size = [[[0, dim1 - 1], dim2], [[0, dim2 - 1], 1]]
    if p[-4] == None:
        IDList = [p[-5]]
    else:
        IDList = list(get_IDs(p[-4]))
        IDList.insert(0, p[-5])
    for ID in IDList:
        qtype = None
        if ID == None:
            continue
        if find(ID, 'dec') != False:
            print(f"Error! Variable '{ID}' already declared!")
            quit()

        if p[-2] == 'int':
            qtype = (0, p[-2])
            if env == 'global':
                address = memory.gbli[0] + memory.gbli[1]
                if address >= memory.gblf[0]:
                    print(f'Error! Too many global integer variables!')
                    quit()
                memory.gbli[1] =  memory.gbli[1] + arr_size[0][1] + 1 if type(arr_size[1]) == int else memory.gbli[1] + tsize
            else:
                address = memory.lcli[0] + memory.lcli[1]
                if address >= memory.lclf[0]:
                    print(f'Error! Too many local integer variables!')
                    quit()
                memory.lcli[1] =  memory.lcli[1] + arr_size[0][1] + 1 if type(arr_size[1]) == int else memory.lcli[1] + tsize

        elif p[-2] == 'float':
            qtype = (1, p[-2])
            if env == 'global':
                address = memory.gblf[0] + memory.gblf[1]
                if address >= memory.gbls[0]:
                    print(f'Error! Too many global float variables!')
                    quit()
                memory.gblf[1] =  memory.gblf[1] + arr_size[0][1] + 1 if type(arr_size[1]) == int else memory.gblf[1] + tsize
            else:
                address = memory.lclf[0] + memory.lclf[1]
                if address >= memory.lcls[0]:
                    print(f'Error! Too many local float variables!')
                    quit()
                memory.lclf[1] =  memory.lclf[1] + arr_size[0][1] + 1 if type(arr_size[1]) == int else memory.lclf[1] + tsize

        else:
            qtype = (2, p[-2])
            if env == 'global':
                address = memory.gbls[0] + memory.gbls[1]
                if address >= memory.lcli[0]:
                    print(f'Error! Too many global string variables!')
                    quit()
                memory.gbls[1] =  memory.gbls[1] + arr_size[0][1] + 1 if type(arr_size[1]) == int else memory.gbls[1] + tsize
            else:
                address = memory.lcls[0] + memory.lcls[1]
                if address >= memory.tmpi[0]:
                    print(f'Error! Too many local string variables!')
                    quit()
                memory.lcls[1] =  memory.lcls[1] + arr_size[0][1] + 1 if type(arr_size[1]) == int else memory.lcls[1] + tsize

        new_var = var_object(ID, qtype, address, arr_size)
        variables.append(new_var)

def p_neuralgic_opr(p):
    '''
    neuralgic_opr :
    '''
    S.Operators.append(p[-1])

def p_neuralgic_int(p):
    '''
    neuralgic_int :
    '''
    constant_handler(p, (0, 'int'))

def p_neuralgic_float(p):
    '''
    neuralgic_float :
    '''
    constant_handler(p, (1, 'float'))

def p_neuralgic_str(p):
    '''
    neuralgic_str :
    '''
    constant_handler(p, (2, 'string'))

def p_neuralgic_var(p):
    '''
    neuralgic_var :
    '''
    var = find(p[-1], 'var')
    if not var:
        print(f"Error! Variable '{p[-1]}' doesn't exist!")
        quit()
    S.Symbols.append(p[-1])
    S.Types.append(var.type)
    if type(var.arr_size[1]) == list or var.arr_size[0][1] > 0:
        global dims
        dims = var
        constant_handler([dims.v_address], (0, 'int'), False)

def p_neuralgic_array(p):
    '''
    neuralgic_array :
    '''
    id = S.Symbols.pop()
    qtype = S.Types.pop()
    global dims
    if not dims:
        print(f"Error! Variable '{id}' is atomic!")
        quit()
    else:
        S.Dimensions.append((id, 1))
        S.Operators.append('[')

def p_evaluate_dimension(p):
    '''
    evaluate_dimension :
    '''
    if S.Types[-1][0] not in [0, 4]:
        print(f"Index error on variable '{dims.ID}'! Indexes must be integer values.")
        quit()
    global dim
    dim = 1
    dimension_tracker(dim)

def p_neuralgic_matrix(p):
    '''
    neuralgic_matrix :
    '''
    global dim
    dim += 1
    dimension_tracker(dim)

def p_end_dimensions(p):
    '''
    end_dimensions :
    '''
    if dim == 1 and type(dims.arr_size[1]) == list:
        print(f"Error! {dims.ID} is a matrix, expected another index.")
        quit()
    aux = S.Symbols.pop()
    pointer = temporary_handler(4)
    baseD = quad_address(dims.v_address)
    quad_gen(('+', quad_address(aux), baseD, pointer))
    S.Operators.pop()

def p_neuralgic_params(p):
    '''
    neuralgic_params :
    '''
    if p[-1] == None:
        return
    else:
        params = []
        qtype = None
        IDList = [ID for ID in list(get_IDs(p[-1])) if ID != None]
        for i in range(1, len(IDList), 2):
            if IDList[i] == 'int':
                qtype = 0
                address = memory.lcli[0] + memory.lcli[1]
                memory.lcli[1] += 1
                params.append((0, address))
            elif IDList[i] == 'float':
                qtype = 1
                address = memory.lclf[0] + memory.lclf[1]
                memory.lclf[1] += 1
                params.append((1, address))
            else:
                qtype = 2
                address = memory.lcls[0] + memory.lcls[1]
                memory.lcls[1] += 1
                params.append((2, address))

            new_var = var_object(IDList[i-1], (qtype, IDList[i]), address, [[0, 0], 1])
            variables.append(new_var)
        funDir.modules[-1].prototyping = params

def p_neuralgic_paren(p):
    '''
    neuralgic_paren :
    '''
    S.Operators.pop()

def p_neuralgic_expr(p):
    '''
    neuralgic_expr :
    '''
    expression_handler(p, p[-3])

def p_neuralgic_unary(p):
    '''
    neuralgic_unary :
    '''
    if p[-2] == '++' or p[-2] == '--':
        unary_handler(p, p[-2])
    else:
        unary_handler(p, p[-3])

def p_neuralgic_print(p):
    '''
    neuralgic_print :
    '''
    global quad_count
    if not S.Symbols:
        print(f"Incorrect value provided to print function!")
        quit()
    if p[-2] == None:
        quad_gen(('LPrint', None, None, None))
    else:
        temp_quads = quadruple_list()
        IDList = list(get_IDs(p[-2]))
        to_remove = []
        for i in range(len(IDList)):
            if IDList[i] == ']' or IDList[i] == ',':
                to_remove.append(IDList[i-1])
                to_remove.append(IDList[i])
            if IDList[i] in ['size', 'mean', 'median', 'mode', 'variance', 'std', 'range', 'sum', 'min', 'max']:
                to_remove.append(IDList[i+1])
        if len(to_remove) > 0:
            IDList = [val for val in IDList if val not in to_remove]
        for i in range(len(IDList)):
            operation = 'Print'
            if i == 0:
                operation = 'LPrint'
            if IDList[i] == None or IDList[i] == '(':
                continue

            msg = quad_address()
            S.Types.pop()
            new_quad = quadruple(operation, None, None, msg)
            temp_quads.append(new_quad)

        temp_quads.quadruples = list(reversed(temp_quads.quadruples))
        for quad in temp_quads.quadruples:
            quadruples.append(quad)
            quad_count += 1

def p_neuralgic_input(p):
    '''
    neuralgic_input :
    '''
    msg = quad_address()
    mtype = S.Types.pop()
    if mtype[0] not in [2, 4]:
        print(f"Error while performing input! '{p[-4]}' is not a string!")
        quit()
    storage = quad_address(p[-2])
    quad_gen(('Input', None, msg, storage))

def p_neuralgic_mirror(p):
    '''
    neuralgic_mirror :
    '''
    if S.Types[-1][0] != 2:
        print("Semantic error in first argument of mirror function! Expected string value.")
        quit()
    filename = quad_address()
    storage = find(p[-3], 'var')
    if storage.type[0] > 1 or type(storage.arr_size[1]) == list:
        print("Semantic error in second argument of mirror function! Expected an unidimensional array of types int or float.")
        quit()

    lsup = storage.arr_size[0][1] + storage.v_address
    quad_gen(('Mirror', filename, storage.v_address, lsup))

def p_verify_ID(p):
    '''
    verify_ID :
    '''
    global fun
    for module in funDir.modules:
        if module.ID == p[-1]:
            fun = module
            break
    if not fun:
        print(f"Error! Module '{p[-1]}' does not exist!")
        quit()

def p_neuralgic_call(p):
    '''
    neuralgic_call :
    '''
    global fun
    if p[-1] == None:
        if fun.prototyping == None:
            quad_gen(('GoSub', None, None, fun.beginning))
            fun = False
            return
        else:
            print(f"Error! No arguments received! Expected {len(fun.prototyping)}.")
            quit()

    IDList = [ID for ID in list((get_IDs(p[-1]))) if ID != None]
    if len(IDList) != None and fun.prototyping == None:
        print(f"Error! Call to '{fun.ID}' received too many arguments! Expected no arguments, received {len(IDList)}.")
        quit()
    if len(IDList) != len(fun.prototyping):
        print(f"Error! Call to '{fun.ID}' received incorrect amount of arguments! Expected {len(fun.prototyping)}, received {len(IDList)}.")
        quit()

    aux = [(S.Symbols.pop(), S.Types.pop()) for i in range(len(IDList))]
    ARE = ['ARE', fun.ID, None, None]
    call_solver(ARE, IDList, aux)

def p_add_call(p):
    '''
    add_call :
    '''
    fun = False
    for module in funDir.modules:
        if module.ID == p[-1][0]:
            fun = module
    if fun.type in ['int', 'float', 'string']:
        typeint = 0 if fun.type == 'int' else 1 if fun.type == 'float' else 2
        temp = temporary_handler(typeint)
        quad_gen(('<-', None, quad_address(fun.ID), temp))

def p_neuralgic_if(p):
    '''
    neuralgic_if :
    '''
    expr_type = S.Types.pop()
    if expr_type[0] != 3:
        print(f'Error! Cannot evaluate the truth value of {expr_type[1]} expressions!')
        quit()

    res = quad_address()
    quad_gen(('GotoF', res, None, None))
    S.Jumps.append(quad_count)

def p_neuralgic_cond(p):
    '''
    neuralgic_cond :
    '''
    end = S.Jumps.pop()
    quadruples.quadruples[end].storage = quad_count + 1

def p_neuralgic_else(p):
    '''
    neuralgic_else :
    '''
    quad_gen(('Goto', None, None, None))
    false = S.Jumps.pop()
    S.Jumps.append(quad_count)
    quadruples.quadruples[false].storage = quad_count + 1

def p_neuralgic_while(p):
    '''
    neuralgic_while :
    '''
    S.Jumps.append(quad_count + 1)

def p_while_expr(p):
    '''
    while_expr :
    '''
    expr_type = S.Types.pop()
    if expr_type[0] != 3:
        print(f'Error! Cannot evaluate the truth value of {expr_type[1]} expressions!')
        quit()
    res = quad_address()
    quad_gen(('GotoF', res, None, None))
    S.Jumps.append(quad_count)

def p_while_end(p):
    '''
    while_end :
    '''
    end = S.Jumps.pop()
    goback = S.Jumps.pop()

    quad_gen(('Goto', None, None, goback))
    quadruples.quadruples[end].storage = quad_count + 1

def p_neuralgic_dw(p):
    '''
    neuralgic_dw :
    '''
    S.Jumps.append(quad_count + 1)

def p_dw_end(p):
    '''
    dw_end :
    '''
    expr_type = S.Types.pop()
    if expr_type[0] != 3:
        print(f'Error! Cannot evaluate the truth value of {expr_type[1]} expressions!')
        quit()
    res = quad_address()
    goback = S.Jumps.pop()
    quad_gen(('GotoT', res, None, goback))

def p_for_id(p):
    '''
    for_id :
    '''
    var = find(p[-1], 'var')
    if not var:
        print(f"Error! Variable '{p[-1]}' not found!")
        quit()
    if var.type[0] > 0:
        print(f"Semantic error! Type mismatch: Expected int, got {var.type[1]}.")
        quit()

    S.Symbols.append(var.ID)
    S.Types.append(var.type)

def p_for_expr(p):
    '''
    for_expr :
    '''
    expr_type = S.Types.pop()
    if expr_type[0] > 0:
        print(f"Semantic error! Type mismatch: Expected int, got {expr_type[1]}.")
        quit()
    expr = quad_address()
    control = quad_address(S.Symbols[len(S.Symbols) - 1])
    control_type = S.Types[len(S.Types) - 1]

    res = get_result((p[-2], control_type[0], expr_type[0]))
    if res is False:
        print(f'Semantic error! Type mismatch: Got {type_izq[1]} and {type_der[1]}!')
        quit()

    quad_gen((p[-2], None, expr, control))

def p_neuralgic_for(p):
    '''
    neuralgic_for :
    '''
    expr_type = S.Types.pop()
    if expr_type[0] > 0:
        print(f"Semantic error! Type mismatch: Expected int, got {expr_type[1]}.")
        quit()
    expr = quad_address()
    control = quad_address(S.Symbols[len(S.Symbols) - 1])
    tn = temporary_handler(3, False)
    vcontrol = temporary_handler(0, False, 'vcontrol')
    vfinal = temporary_handler(0, False, 'vfinal')
    quad_gen(('<-', None, expr, vfinal))
    quad_gen(('<-', None, control, vcontrol))
    quad_gen(('<', vcontrol, vfinal, tn))

    S.Jumps.append(quad_count)
    quad_gen(('GotoF', tn, None, None))
    S.Jumps.append(quad_count)

def p_for_end(p):
    '''
    for_end :
    '''
    tn = temporary_handler(0, False)
    constant_handler([1], (0, 'int'), False)
    one = find(1, 'cte')
    control = quad_address(S.Symbols[len(S.Symbols) - 1])
    vcontrol = find('vcontrol', 'var')
    quad_gen(('+', vcontrol.v_address, one.v_address, tn))
    quad_gen(('<-', None, tn, vcontrol.v_address))
    quad_gen(('<-', None, tn, control))

    end = S.Jumps.pop()
    goback = S.Jumps.pop()
    quad_gen(('Goto', None, None, goback))
    quadruples.quadruples[end].storage = quad_count + 1

    S.Symbols.pop()
    S.Types.pop()

def p_neuralgic_stats(p):
    '''
    neuralgic_stats :
    '''
    qtype = 0 if p[-1][0] == 'size' else -1 if p[-1][0] == 'range' else 1
    res = find(p[-1][1], 'var')
    qtype = 0 if res.type[0] == 0 and p[-1][0] in ['mode', 'sum', 'min', 'max'] else 1
    address = temporary_handler(qtype) if qtype >= 0 else None
    if not res:
        print(f"Error! Variable '{p[-1][1]}' does not exist!")
        quit()
    if res.arr_size[0][1] == 0 or type(res.arr_size[1]) == list:
        print(f"Error! Variable '{p[-1][1]}' is not an unidimensional array!")
        quit()
    if res.type[0] > 1:
        print(f"Error! Variable '{p[-1][1]}' does not contain numeric values!")
        quit()
    lsup = res.arr_size[0][1] + res.v_address
    quad_gen((p[-1][0].capitalize(), res.v_address, lsup, address))

def p_neuralgic_xplot(p):
    '''
    neuralgic_xplot :
    '''
    array = find(p[-5], 'var')
    filename = p[-3][1:-1].split('.')
    if len(filename) != 2:
        print('Error! Incorrect filename provided.')
        quit()
    extensions = ['jpeg', 'png', 'html', 'json', 'svg', 'webp', 'pdf']
    if filename[1] not in extensions:
        print(f"Error! {filename[1]} export format not supported! Supported formats are {', '.join(extensions)}.")
        quit()
    constant_handler([p[-3]], (2, 'string'))
    filename = quad_address()
    lsup = array.arr_size[0][1] + array.v_address
    quad_gen((p[-7].capitalize(), array.v_address, lsup, filename))

def p_neuralgic_xyplot(p):
    '''
    neuralgic_xyplot :
    '''
    yarray = find(p[-5], 'var')
    xarray = find(p[-7], 'var')
    filename = p[-3][1:-1].split('.')
    if len(filename) != 2:
        print('Error! Incorrect filename provided.')
        quit()
    extensions = ['jpeg', 'png', 'html', 'json', 'svg', 'webp', 'pdf']
    if filename[1] not in extensions:
        print(f"Error! {filename[1]} export format not supported! Supported formats are {', '.join(extensions)}.")
        quit()
    constant_handler([p[-3]], (2, 'string'))
    filename = quad_address()
    lsup1 = xarray.arr_size[0][1] + xarray.v_address
    lsup2 = yarray.arr_size[0][1] + yarray.v_address
    quad_gen((p[-9].capitalize(), xarray.v_address, lsup1, filename))
    quad_gen((p[-9].capitalize(), yarray.v_address, lsup2, filename))

def p_neuralgic_return(p):
    '''
    neuralgic_return :
    '''
    if env not in ['int', 'float', 'string']:
        print(f"Error! Cannot return in '{env}' context!")
        quit()

    result_type = S.Types.pop()
    if env != result_type[1]:
        print(f"Error! Return type mismatch! Expected {env}, got {result_type[1]}.")
        quit()

    result = quad_address()
    storage = quad_address(funDir.modules[-1].ID)
    quad_gen(('Return', None, result, storage))

#------------------------------Aux Rules----------------------------------------
def p_empty(p):
    '''
    empty :
    '''
    p[0] = None

def p_error(t):
    if t is not None:
        print(f"Line {t.lineno}, illegal token: {t.value}.")
    else:
        print('Unexpected end of input.')
    quit()

parser = yacc.yacc()

try:
    test_file = open(argv[1])
    source_code = test_file.read()
    test_file.close()
    parser.parse(source_code)
except FileNotFoundError:
    print(f'Error! File {argv[1]} not found!')
    quit()
